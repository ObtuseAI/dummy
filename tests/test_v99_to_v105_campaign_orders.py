from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v99_reports import generate_all_v99_reports_for_tests
from scripts.generate_v100_reports import generate_all_v100_reports_for_tests
from scripts.generate_v101_reports import generate_all_v101_reports_for_tests
from scripts.generate_v102_reports import generate_all_v102_reports_for_tests
from scripts.generate_v103_reports import generate_all_v103_reports_for_tests
from scripts.generate_v104_reports import generate_all_v104_reports_for_tests
from scripts.generate_v105_reports import generate_all_v105_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe

CAMPAIGN = {"exact_phrase": sgc.MICRO_CAMPAIGN_PHRASE, "operator": "op", "timestamp": "t", "reason": "r", "scope": sgc.MICRO_CAMPAIGN_SCOPE, "expiration": "e"}


def order_approval(phrase: str = sgc.CAMPAIGN_PER_ORDER_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "submit one tiny live limit campaign order via firewall", "scope": sgc.CAMPAIGN_PER_ORDER_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "no_automatic_repeat_acknowledgment": "no automatic repeat", "caps_unchanged_acknowledgment": "caps unchanged unless separately approved",
        "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "rollback_acknowledgment": "immediate fail-closed rollback", "firewall_only_acknowledgment": "firewall only",
    }


class FakeFirewall:
    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False}


# --- V99 order 1 ---
def test_v99_default_no_submit_and_full_auth_double() -> None:
    default = generate_all_v99_reports_for_tests()["v99_order_1_canary_controller_report.json"]
    assert_staged_safe(default)
    assert default["order_1_canary_controller_status"] == "PARTIAL_ORDER1_NOT_ARMED"
    assert default["real_live_orders_submitted_count"] == 0
    c = generate_all_v99_reports_for_tests(campaign_approval=CAMPAIGN, order_approval=order_approval(), v98_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v99-attempt-1"))["v99_order_1_canary_controller_report.json"]
    assert c["order_1_canary_controller_status"] == "PASS_ORDER1_SUBMITTED"
    assert c["order_attempt_id"] == "v99-attempt-1"
    assert c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False
    assert c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v99_fuzzy_and_no_adapter_block() -> None:
    fuzzy = generate_all_v99_reports_for_tests(campaign_approval=CAMPAIGN, order_approval=order_approval("bad"), v98_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v99_order_1_canary_controller_report.json"]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v99_reports_for_tests(campaign_approval=CAMPAIGN, order_approval=order_approval(), v98_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True)["v99_order_1_canary_controller_report.json"]
    assert no_adapter["firewall_submit_invoked"] is False
    assert no_adapter["real_live_orders_submitted_count"] == 0


# --- V100 / V101 ---
def test_v100_v101_reconcile_and_review_with_override() -> None:
    d100 = generate_all_v100_reports_for_tests()["v100_reconcile_controller_report.json"]
    assert d100["reconcile_controller_status"] == "PARTIAL_NO_ORDER1_TO_RECONCILE"
    r100 = generate_all_v100_reports_for_tests(v99_final_override={"order_1_canary_controller_status": "PASS_ORDER1_SUBMITTED", "simulated_order_submits_count": 1, "order_attempt_id": "v99-attempt-1"})["v100_reconcile_controller_report.json"]
    assert r100["reconcile_controller_status"] == "PASS_ORDER1_RECONCILED_AUTOLOCKED"
    assert r100["forensic_capture"]["private_data_leaked"] is False

    d101 = generate_all_v101_reports_for_tests()["v101_forensic_review_controller_report.json"]
    assert d101["forensic_review_controller_status"] == "PARTIAL_NO_ORDER1_TO_REVIEW"
    r101 = generate_all_v101_reports_for_tests(v100_final_override={"reconcile_controller_status": "PASS_ORDER1_RECONCILED_AUTOLOCKED", "verdict": "PASS"})["v101_forensic_review_controller_report.json"]
    assert r101["forensic_review_controller_status"] == "PASS_ORDER1_FORENSIC_REVIEWED"
    assert r101["new_order_placed"] is False
    assert_staged_safe(r101)


# --- V102 / V103 ---
def test_v102_gate_and_v103_order2_submit() -> None:
    d102 = generate_all_v102_reports_for_tests()["v102_order_2_gate_controller_report.json"]
    assert d102["order_2_gate_controller_status"] == "PARTIAL_ORDER2_APPROVAL_OR_ORDER1_PROOF_ABSENT"
    r102 = generate_all_v102_reports_for_tests(campaign_approval=CAMPAIGN, order_2_approval=order_approval(), order_1_reconciled_override=True, order_1_forensic_override=True)["v102_order_2_gate_controller_report.json"]
    assert r102["order_2_gate_controller_status"] == "PASS_ORDER2_GATE_READY_NO_SUBMIT"

    d103 = generate_all_v103_reports_for_tests()["v103_order_2_canary_controller_report.json"]
    assert d103["order_2_canary_controller_status"] == "PARTIAL_ORDER2_NOT_ARMED"
    assert d103["real_live_orders_submitted_count"] == 0
    c103 = generate_all_v103_reports_for_tests(campaign_approval=CAMPAIGN, order_approval=order_approval(), v102_ready_override=True, order_1_reconciled_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v103-attempt-1"))["v103_order_2_canary_controller_report.json"]
    assert c103["order_2_canary_controller_status"] == "PASS_ORDER2_SUBMITTED"
    assert c103["order_attempt_id"] == "v103-attempt-1"
    assert c103["real_live_orders_submitted_count"] == 0
    assert c103["real_broker_contacted"] is False
    assert_staged_safe(c103)


# --- V104 ---
def test_v104_stop_continue() -> None:
    d = generate_all_v104_reports_for_tests()["v104_reconcile_review_controller_report.json"]
    assert d["stop_continue_decision"] == "PARTIAL_NO_ORDER2_TO_REVIEW"
    cont = generate_all_v104_reports_for_tests(v103_final_override={"order_2_canary_controller_status": "PASS_ORDER2_SUBMITTED", "simulated_order_submits_count": 1})["v104_reconcile_review_controller_report.json"]
    assert cont["stop_continue_decision"] == "CONTINUE_ALLOWED_WITH_ORDER3_APPROVAL"
    stop = generate_all_v104_reports_for_tests(v103_final_override={"order_2_canary_controller_status": "PASS_ORDER2_SUBMITTED", "simulated_order_submits_count": 1}, stop_signal="STOP_DRIFT_LOCK")["v104_reconcile_review_controller_report.json"]
    assert stop["stop_continue_decision"] == "STOP_DRIFT_LOCK"


# --- V105 order 3 + closeout ---
def test_v105_default_blocked_full_auth_submits_and_closes() -> None:
    d = generate_all_v105_reports_for_tests()["v105_order_3_controller_report.json"]
    assert d["order_3_controller_status"] == "PARTIAL_ORDER3_BLOCKED"
    assert d["real_live_orders_submitted_count"] == 0
    c = generate_all_v105_reports_for_tests(campaign_approval=CAMPAIGN, order_approval=order_approval(), continuation_allowed_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v105-attempt-1"))["v105_order_3_controller_report.json"]
    assert c["order_3_controller_status"] == "PASS_ORDER3_SUBMITTED_CAMPAIGN_CLOSED"
    assert c["campaign_closed"] is True
    assert c["further_campaign_orders_allowed"] is False
    assert c["scale_applied"] is False
    assert c["real_live_orders_submitted_count"] == 0
    assert_staged_safe(c)


def test_v99_to_v105_safety_and_locks_default() -> None:
    for gen in (generate_all_v99_reports_for_tests, generate_all_v100_reports_for_tests, generate_all_v101_reports_for_tests, generate_all_v102_reports_for_tests, generate_all_v103_reports_for_tests, generate_all_v104_reports_for_tests, generate_all_v105_reports_for_tests):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
