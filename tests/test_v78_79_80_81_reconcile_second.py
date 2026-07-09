from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v78_reports import generate_all_v78_reports_for_tests
from scripts.generate_v79_reports import generate_all_v79_reports_for_tests
from scripts.generate_v80_reports import generate_all_v80_reports_for_tests
from scripts.generate_v81_reports import generate_all_v81_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe

SUBMITTED_V77 = {"live_canary_controller_status": "PASS_LIVE_CANARY_SUBMITTED", "simulated_canary_submits_count": 1, "order_attempt_id": "v77-attempt-1", "verdict": "PASS"}
RECONCILED_V78 = {"reconcile_controller_status": "PASS_LIVE_CANARY_RECONCILED", "verdict": "PASS"}


def second_packet(phrase: str = sgc.V81_SECOND_CANARY_SUBMIT_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "arm and submit one second tiny live limit canary via firewall", "scope": sgc.V81_SECOND_CANARY_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "max_one_order_acknowledgment": "exactly one order",
        "limit_only_acknowledgment": "limit only", "no_market_order_acknowledgment": "no market order",
        "firewall_only_acknowledgment": "firewall only", "rollback_acknowledgment": "immediate fail-closed rollback",
        "first_canary_reconcile_passed_acknowledgment": "first-canary reconcile passed",
        "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "caps_unchanged_acknowledgment": "caps unchanged unless separately approved",
    }


class FakeFirewall:
    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": "v81-attempt-1", "accepted": True, "real_broker_contacted": False, "market_order": False}


def test_v78_default_no_canary_reconciles_with_override() -> None:
    default = generate_all_v78_reports_for_tests()["v78_reconcile_controller_report.json"]
    assert default["reconcile_controller_status"] == "PARTIAL_NO_LIVE_CANARY_TO_RECONCILE"
    assert_staged_safe(default)
    reconciled = generate_all_v78_reports_for_tests(v77_final_override=SUBMITTED_V77, outcome_state="FILLED")["v78_reconcile_controller_report.json"]
    assert reconciled["reconcile_controller_status"] == "PASS_LIVE_CANARY_RECONCILED"
    assert reconciled["forensic_capture_status"] == "PASS_FORENSICS_CAPTURED"
    assert reconciled["forensic_capture"]["private_data_leaked"] is False
    assert reconciled["real_live_orders_submitted_count"] == 0


def test_v79_default_no_canary_reviews_with_override() -> None:
    default = generate_all_v79_reports_for_tests()["v79_forensic_review_controller_report.json"]
    assert default["forensic_review_controller_status"] == "PARTIAL_NO_LIVE_CANARY_TO_REVIEW"
    reviewed = generate_all_v79_reports_for_tests(v78_final_override=RECONCILED_V78)["v79_forensic_review_controller_report.json"]
    assert reviewed["forensic_review_controller_status"] == "PASS_FIRST_LIVE_CANARY_FORENSIC_REVIEWED"
    assert reviewed["new_order_placed"] is False
    assert_staged_safe(reviewed)


def test_v80_partial_default_ready_with_override() -> None:
    default = generate_all_v80_reports_for_tests()["v80_repeat_canary_validator_report.json"]
    assert default["repeat_canary_validator_status"] in {"PARTIAL_SECOND_CANARY_APPROVAL_ABSENT", "PARTIAL_FIRST_CANARY_PROOF_ABSENT"}
    ready = generate_all_v80_reports_for_tests(approval_input=second_packet(), first_canary_reconciled_override=True, first_canary_forensic_override=True)["v80_repeat_canary_validator_report.json"]
    assert ready["repeat_canary_validator_status"] == "PASS_SECOND_CANARY_APPROVAL_VALID_STRICTER_GATE"
    assert_staged_safe(ready)


def test_v80_fuzzy_second_approval_fails_closed() -> None:
    controller = generate_all_v80_reports_for_tests(approval_input=second_packet("I approve a second canary"), first_canary_reconciled_override=True, first_canary_forensic_override=True)["v80_repeat_canary_validator_report.json"]
    assert controller["repeat_canary_validator_status"] == "FAIL_CLOSED_INVALID_SECOND_APPROVAL"


def test_v81_default_no_submit() -> None:
    controller = generate_all_v81_reports_for_tests()["v81_second_canary_controller_report.json"]
    assert_staged_safe(controller)
    assert controller["second_canary_controller_status"] == "PARTIAL_SECOND_CANARY_NOT_ARMED"
    assert controller["real_live_orders_submitted_count"] == 0
    assert controller["firewall_submit_invoked"] is False


def test_v81_first_canary_proof_absent_blocks_even_with_approval() -> None:
    controller = generate_all_v81_reports_for_tests(approval_input=second_packet(), v80_ready_override=True, first_canary_reconciled_override=False, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall())["v81_second_canary_controller_report.json"]
    assert controller["firewall_submit_invoked"] is False
    assert controller["real_live_orders_submitted_count"] == 0


def test_v81_full_authority_injected_double_records_single_attempt_no_real_order() -> None:
    reports = generate_all_v81_reports_for_tests(approval_input=second_packet(), v80_ready_override=True, first_canary_reconciled_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall())
    controller = reports["v81_second_canary_controller_report.json"]
    assert controller["second_canary_controller_status"] == "PASS_SECOND_CANARY_SUBMITTED"
    assert controller["single_submit_locked"] is True
    assert controller["order_attempt_id"] == "v81-attempt-1"
    assert controller["real_live_orders_submitted_count"] == 0
    assert controller["real_broker_contacted"] is False
    assert controller["market_order_submitted"] is False
    assert controller["automatic_campaign_started"] is False
    assert reports["final_report_v81.json"]["verdict"] == "PASS"
    assert_staged_safe(controller)
