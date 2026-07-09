from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v89_reports import generate_all_v89_reports_for_tests
from scripts.generate_v90_reports import generate_all_v90_reports_for_tests
from scripts.generate_v91_reports import generate_all_v91_reports_for_tests
from scripts.generate_v92_reports import generate_all_v92_reports_for_tests
from scripts.generate_v93_reports import generate_all_v93_reports_for_tests
from scripts.generate_v94_reports import generate_all_v94_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe

CAMPAIGN = {"exact_phrase": sgc.MICRO_CAMPAIGN_PHRASE, "operator": "op", "timestamp": "t", "reason": "r", "scope": sgc.MICRO_CAMPAIGN_SCOPE, "expiration": "e"}


def per_order(phrase: str = sgc.CAMPAIGN_PER_ORDER_PHRASE) -> dict:
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


# --- V89 order 1 ---
def test_v89_default_no_submit() -> None:
    c = generate_all_v89_reports_for_tests()["v89_order_1_gate_controller_report.json"]
    assert_staged_safe(c)
    assert c["order_1_gate_controller_status"] == "PARTIAL_ORDER_1_NOT_ARMED"
    assert c["real_live_orders_submitted_count"] == 0
    assert c["firewall_submit_invoked"] is False


def test_v89_fuzzy_order_approval_blocks() -> None:
    c = generate_all_v89_reports_for_tests(campaign_approval=CAMPAIGN, order_approval=per_order("I approve an order"), v88_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v89"))["v89_order_1_gate_controller_report.json"]
    assert c["firewall_submit_invoked"] is False
    assert c["real_live_orders_submitted_count"] == 0


def test_v89_full_authority_injected_double_single_attempt_no_real_order() -> None:
    reports = generate_all_v89_reports_for_tests(campaign_approval=CAMPAIGN, order_approval=per_order(), v88_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v89-attempt-1"))
    c = reports["v89_order_1_gate_controller_report.json"]
    assert c["order_1_gate_controller_status"] == "PASS_ORDER_1_SUBMITTED"
    assert c["single_submit_locked"] is True
    assert c["order_attempt_id"] == "v89-attempt-1"
    assert c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False
    assert c["market_order_submitted"] is False
    assert reports["final_report_v89.json"]["verdict"] == "PASS"
    assert_staged_safe(c)


# --- V90 reconcile ---
def test_v90_default_no_order_1_reconciles_with_override() -> None:
    default = generate_all_v90_reports_for_tests()["v90_reconcile_controller_report.json"]
    assert default["reconcile_controller_status"] == "PARTIAL_NO_ORDER_1_TO_RECONCILE"
    rec = generate_all_v90_reports_for_tests(v89_final_override={"order_1_gate_controller_status": "PASS_ORDER_1_SUBMITTED", "simulated_order_submits_count": 1, "order_attempt_id": "v89-attempt-1"})["v90_reconcile_controller_report.json"]
    assert rec["reconcile_controller_status"] == "PASS_ORDER_1_RECONCILED"
    assert rec["forensic_capture"]["private_data_leaked"] is False
    assert_staged_safe(rec)


# --- V91 order 2 ---
def test_v91_default_blocked_full_auth_submits_double() -> None:
    default = generate_all_v91_reports_for_tests()["v91_order_2_gate_controller_report.json"]
    assert default["order_2_gate_controller_status"] == "PARTIAL_ORDER_2_BLOCKED_MISSING_ORDER_1_PROOF_OR_APPROVAL"
    assert default["real_live_orders_submitted_count"] == 0
    c = generate_all_v91_reports_for_tests(campaign_approval=CAMPAIGN, order_approval=per_order(), order_1_reconciled_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v91-attempt-1"))["v91_order_2_gate_controller_report.json"]
    assert c["order_2_gate_controller_status"] == "PASS_ORDER_2_SUBMITTED"
    assert c["order_attempt_id"] == "v91-attempt-1"
    assert c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False
    assert_staged_safe(c)


def test_v91_order_1_proof_absent_blocks() -> None:
    c = generate_all_v91_reports_for_tests(campaign_approval=CAMPAIGN, order_approval=per_order(), order_1_reconciled_override=False, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v91"))["v91_order_2_gate_controller_report.json"]
    assert c["firewall_submit_invoked"] is False
    assert c["real_live_orders_submitted_count"] == 0


# --- V92 order 2 reconcile / stop-continue ---
def test_v92_default_no_order_2_continue_with_override() -> None:
    default = generate_all_v92_reports_for_tests()["v92_reconcile_review_controller_report.json"]
    assert default["stop_continue_decision"] == "PARTIAL_NO_ORDER_2_TO_REVIEW"
    cont = generate_all_v92_reports_for_tests(v91_final_override={"order_2_gate_controller_status": "PASS_ORDER_2_SUBMITTED", "simulated_order_submits_count": 1})["v92_reconcile_review_controller_report.json"]
    assert cont["stop_continue_decision"] == "CONTINUE_ALLOWED_WITH_ORDER_3_APPROVAL"
    stop = generate_all_v92_reports_for_tests(v91_final_override={"order_2_gate_controller_status": "PASS_ORDER_2_SUBMITTED", "simulated_order_submits_count": 1}, stop_signal="STOP_LOSS_LOCK")["v92_reconcile_review_controller_report.json"]
    assert stop["stop_continue_decision"] == "STOP_LOSS_LOCK"


# --- V93 order 3 + closeout ---
def test_v93_default_blocked_full_auth_submits_and_closes() -> None:
    default = generate_all_v93_reports_for_tests()["v93_order_3_gate_controller_report.json"]
    assert default["order_3_gate_controller_status"] == "PARTIAL_ORDER_3_BLOCKED"
    assert default["real_live_orders_submitted_count"] == 0
    c = generate_all_v93_reports_for_tests(campaign_approval=CAMPAIGN, order_approval=per_order(), continuation_allowed_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v93-attempt-1"))["v93_order_3_gate_controller_report.json"]
    assert c["order_3_gate_controller_status"] == "PASS_ORDER_3_SUBMITTED_CAMPAIGN_CLOSED"
    assert c["campaign_closed"] is True
    assert c["further_campaign_orders_allowed"] is False
    assert c["real_live_orders_submitted_count"] == 0
    assert_staged_safe(c)


# --- V94 final audit ---
def test_v94_final_audit_production_locked_no_scale() -> None:
    reports = generate_all_v94_reports_for_tests()
    c = reports["v94_final_campaign_audit_controller_report.json"]
    assert_staged_safe(c)
    assert c["final_campaign_audit_controller_status"] == "PASS_CAMPAIGN_AUDITED_PRODUCTION_LOCKED"
    assert c["production_gate_status"] == "PASS_PRODUCTION_GATE_LOCKED"
    assert c["autonomous_trading_enabled"] is False
    assert c["scale_recommendation"] == "NO_SCALE"
    assert c["scale_applied"] is False
    assert c["production_gate"]["AUTONOMOUS_TRADING_DISABLED"] is True
    assert reports["final_report_v94.json"]["verdict"] == "PASS"


def test_v89_to_v94_safety_and_locks_default() -> None:
    for gen in (generate_all_v89_reports_for_tests, generate_all_v90_reports_for_tests, generate_all_v91_reports_for_tests, generate_all_v92_reports_for_tests, generate_all_v93_reports_for_tests, generate_all_v94_reports_for_tests):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
