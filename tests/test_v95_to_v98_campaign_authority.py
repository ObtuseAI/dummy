from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v95_reports import generate_all_v95_reports_for_tests
from scripts.generate_v96_reports import generate_all_v96_reports_for_tests
from scripts.generate_v97_reports import generate_all_v97_reports_for_tests
from scripts.generate_v98_reports import generate_all_v98_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


class FakeFirewall:
    def submit(self, order):
        return {"order_attempt_id": "x", "accepted": True, "real_broker_contacted": False}


def campaign_approval() -> dict:
    return {"exact_phrase": sgc.MICRO_CAMPAIGN_PHRASE, "operator": "op", "timestamp": "t", "reason": "r", "scope": sgc.MICRO_CAMPAIGN_SCOPE, "expiration": "e"}


def order_approval(phrase: str = sgc.CAMPAIGN_PER_ORDER_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "submit one tiny live limit campaign order via firewall", "scope": sgc.CAMPAIGN_PER_ORDER_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "no_automatic_repeat_acknowledgment": "no automatic repeat", "caps_unchanged_acknowledgment": "caps unchanged unless separately approved",
        "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "rollback_acknowledgment": "immediate fail-closed rollback", "firewall_only_acknowledgment": "firewall only",
    }


def test_v95_blocker_audit_passes() -> None:
    reports = generate_all_v95_reports_for_tests()
    c = reports["v95_blocker_closure_controller_report.json"]
    assert_staged_safe(c)
    assert c["v94_baseline_status"] == "PASS_V94_BASELINE_READBACK"
    assert c["blocker_closure_controller_status"] == "PASS_CAMPAIGN_BLOCKERS_CLASSIFIED_V2_NO_SUBMIT"
    assert c["no_broker_contact_proof_status"] == "PASS_NO_BROKER_CONTACT"
    assert c["broker_contacted"] is False
    assert c["current_next_action"] == "AWAIT_CAMPAIGN_ORDER1_AUTHORITY"
    assert reports["final_report_v95.json"]["verdict"] == "PASS"


def test_v96_partial_default_pass_with_both_approvals() -> None:
    default = generate_all_v96_reports_for_tests()["v96_approval_validator_controller_report.json"]
    assert default["approval_validator_controller_status"] == "PARTIAL_CAMPAIGN_OR_ORDER1_APPROVAL_ABSENT"
    assert_staged_safe(default)
    ok = generate_all_v96_reports_for_tests(campaign_approval=campaign_approval(), order_1_approval=order_approval())["v96_approval_validator_controller_report.json"]
    assert ok["approval_validator_controller_status"] == "PASS_CAMPAIGN_AND_ORDER1_APPROVAL_VALID_NO_SUBMIT"
    assert ok["raw_phrase_serialized"] is False
    fuzzy = generate_all_v96_reports_for_tests(campaign_approval=campaign_approval(), order_1_approval=order_approval("I approve an order"))["v96_approval_validator_controller_report.json"]
    assert fuzzy["approval_validator_controller_status"] == "FAIL_CLOSED_INVALID_APPROVAL"


def test_v97_partial_default_ready_with_config_adapter() -> None:
    default = generate_all_v97_reports_for_tests()["v97_readiness_controller_report.json"]
    assert default["readiness_controller_status"] == "PARTIAL_LIVE_CONFIG_OR_FIREWALL_ADAPTER_ABSENT"
    assert default["broker_contacted"] is False
    ready = generate_all_v97_reports_for_tests(live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall())["v97_readiness_controller_report.json"]
    assert ready["readiness_controller_status"] == "PASS_LIVE_CONFIG_CAPS_FIREWALL_BROKER_READY_NO_CONTACT"
    assert ready["broker_contacted"] is False
    assert_staged_safe(ready)


def test_v98_partial_default_ready_with_overrides() -> None:
    default = generate_all_v98_reports_for_tests()["v98_order_1_authorization_controller_report.json"]
    assert default["order_1_authorization_controller_status"] == "PARTIAL_ORDER1_AUTHORIZATION_BLOCKED"
    ready = generate_all_v98_reports_for_tests(v96_ready_override=True, v97_ready_override=True)["v98_order_1_authorization_controller_report.json"]
    assert ready["order_1_authorization_controller_status"] == "PASS_ORDER1_AUTHORIZATION_READY_NO_SUBMIT"
    assert ready["order_submission_present"] is False
    assert_staged_safe(ready)


def test_v95_98_safety_and_locks() -> None:
    for gen in (generate_all_v95_reports_for_tests, generate_all_v96_reports_for_tests, generate_all_v97_reports_for_tests, generate_all_v98_reports_for_tests):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
