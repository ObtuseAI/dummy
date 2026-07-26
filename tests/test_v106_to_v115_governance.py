from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from predator_mesh.report_runtime import generate_all_v106_reports_for_tests
from predator_mesh.report_runtime import generate_all_v107_reports_for_tests
from predator_mesh.report_runtime import generate_all_v108_reports_for_tests
from predator_mesh.report_runtime import generate_all_v109_reports_for_tests
from predator_mesh.report_runtime import generate_all_v110_reports_for_tests
from predator_mesh.report_runtime import generate_all_v111_reports_for_tests
from predator_mesh.report_runtime import generate_all_v112_reports_for_tests
from predator_mesh.report_runtime import generate_all_v113_reports_for_tests
from predator_mesh.report_runtime import generate_all_v114_reports_for_tests
from predator_mesh.report_runtime import generate_all_v115_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def scale_approval(phrase: str = sgc.SCALE_STEP_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review scale step 1 only", "scope": sgc.SCALE_STEP_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def session_approval(phrase: str = sgc.CONTROLLED_SESSION_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "run one controlled live session canary via firewall", "scope": sgc.CONTROLLED_SESSION_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "strict_caps_acknowledgment": "strict caps", "per_order_fail_closed_acknowledgment": "per-order fail-closed checks",
        "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "session_auto_lock_acknowledgment": "immediate session auto-lock",
    }


def autonomy_approval(phrase: str = sgc.AUTONOMY_REVIEW_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review limited autonomy eligibility only", "scope": sgc.AUTONOMY_REVIEW_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


class FakeFirewall:
    """NON-broker firewall double. Never contacts a real broker; asserts no market orders."""

    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False, "session_id": order.get("session_id")}


# --- V106 campaign final forensic audit ---
def test_v106_campaign_audit_pass_and_no_new_order() -> None:
    d = generate_all_v106_reports_for_tests()["v106_campaign_audit_controller_report.json"]
    assert d["campaign_audit_controller_status"] == "PASS_CAMPAIGN_AUDITED_BLOCKED_AND_CLOSED"
    assert d["new_order_placed"] is False
    assert d["real_live_orders_submitted_count"] == 0
    assert_staged_safe(d)
    partial = generate_all_v106_reports_for_tests(v105_final_override={})["v106_campaign_audit_controller_report.json"]
    assert partial["campaign_audit_controller_status"] == "PARTIAL_CAMPAIGN_DATA_UNAVAILABLE"


# --- V107 scale-step approval validator ---
def test_v107_default_absent_and_fixture_review_only() -> None:
    d = generate_all_v107_reports_for_tests()["v107_scale_approval_controller_report.json"]
    assert d["scale_approval_controller_status"] == "PARTIAL_SCALE_APPROVAL_ABSENT"
    assert d["scale_applied"] is False and d["caps_changed"] is False
    ok = generate_all_v107_reports_for_tests(scale_approval=scale_approval())["v107_scale_approval_controller_report.json"]
    assert ok["scale_approval_controller_status"] == "PASS_SCALE_APPROVAL_VALID_REVIEW_ONLY_NO_SCALE"
    assert ok["scale_applied"] is False and ok["caps_changed"] is False
    fuzzy = generate_all_v107_reports_for_tests(scale_approval=scale_approval("bad phrase"))["v107_scale_approval_controller_report.json"]
    assert fuzzy["scale_approval_controller_status"] == "FAIL_CLOSED_INVALID_SCALE_APPROVAL"
    assert_staged_safe(ok)


# --- V108 risk governor hardening ---
def test_v108_risk_policies_locked_no_caps_change() -> None:
    d = generate_all_v108_reports_for_tests()["v108_risk_hardening_controller_report.json"]
    assert d["risk_hardening_controller_status"] == "PASS_RISK_POLICIES_GENERATED_AND_LOCKED"
    assert d["kill_switch_status"] == "PASS_KILL_SWITCH_ARMED"
    assert d["caps_modified"] is False and d["scale_applied"] is False
    assert_staged_safe(d)


# --- V109 abstention governor ---
def test_v109_abstention_active_no_autonomy() -> None:
    d = generate_all_v109_reports_for_tests()["v109_abstention_governor_controller_report.json"]
    assert d["abstention_governor_status"] == "PASS_ABSTENTION_POLICY_ACTIVE"
    assert d["autonomous_trading_enabled"] is False
    assert d["abstention_rules_count"] == 13
    assert_staged_safe(d)


# --- V110 production readiness audit ---
def test_v110_controlled_operation_eligible_locked() -> None:
    d = generate_all_v110_reports_for_tests(prereq_override=True)["v110_production_readiness_controller_report.json"]
    assert d["production_eligibility_status"] == "CONTROLLED_OPERATION_ELIGIBLE_LOCKED"
    assert d["production_enabled"] is False
    blocked = generate_all_v110_reports_for_tests(prereq_override=False)["v110_production_readiness_controller_report.json"]
    assert blocked["production_eligibility_status"] == "PRODUCTION_NOT_READY_BLOCKED"
    assert blocked["production_enabled"] is False
    assert_staged_safe(d)


# --- V111 scale gate ---
def test_v111_scale_gate_reviewed_no_caps_change() -> None:
    d = generate_all_v111_reports_for_tests()["v111_scale_gate_controller_report.json"]
    assert d["scale_gate_controller_status"] == "PASS_SCALE_GATE_REVIEWED_NO_SCALE_APPLIED"
    assert d["scale_recommendation"] == "NO_SCALE"
    assert d["caps_changed"] is False and d["scale_applied"] is False
    ready = generate_all_v111_reports_for_tests(scale_approved_override=True, production_ready_override=True)["v111_scale_gate_controller_report.json"]
    assert ready["scale_recommendation"] == "SCALE_STEP_1_REVIEW_READY"
    assert ready["caps_changed"] is False
    assert_staged_safe(ready)


# --- V112 session governor ---
def test_v112_session_governor_ready_locked() -> None:
    d = generate_all_v112_reports_for_tests()["v112_session_governor_controller_report.json"]
    assert d["session_governor_status"] == "PASS_SESSION_GOVERNOR_READY_LOCKED"
    assert d["session_live_orders"] == 0
    assert d["no_auto_submit_proof_status"] == "PASS_NO_AUTO_SUBMIT"
    assert_staged_safe(d)


# --- V113 controlled live session canary ---
def test_v113_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v113_reports_for_tests()["v113_session_canary_controller_report.json"]
    assert d["session_canary_controller_status"] == "PARTIAL_SESSION_CANARY_NOT_ARMED"
    assert d["session_live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v113_reports_for_tests(session_approval=session_approval(), session_governor_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, per_order_mode=True, firewall_adapter=FakeFirewall("v113-attempt-1"))["v113_session_canary_controller_report.json"]
    assert c["session_canary_controller_status"] == "PASS_SESSION_CANARY_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v113-attempt-1"
    assert c["session_locked"] is True
    assert c["session_live_orders"] == 0
    assert c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False
    assert c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v113_fuzzy_and_no_adapter_block() -> None:
    fuzzy = generate_all_v113_reports_for_tests(session_approval=session_approval("bad"), session_governor_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, per_order_mode=True, firewall_adapter=FakeFirewall("x"))["v113_session_canary_controller_report.json"]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v113_reports_for_tests(session_approval=session_approval(), session_governor_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, per_order_mode=True)["v113_session_canary_controller_report.json"]
    assert no_adapter["firewall_submit_invoked"] is False
    assert no_adapter["session_live_orders"] == 0


# --- V114 session reconcile ---
def test_v114_default_partial_and_override_reconciled() -> None:
    d = generate_all_v114_reports_for_tests()["v114_session_reconcile_controller_report.json"]
    assert d["session_reconcile_controller_status"] == "PARTIAL_NO_SESSION_CANARY_TO_RECONCILE"
    r = generate_all_v114_reports_for_tests(v113_final_override={"session_canary_controller_status": "PASS_SESSION_CANARY_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1})["v114_session_reconcile_controller_report.json"]
    assert r["session_reconcile_controller_status"] == "PASS_SESSION_RECONCILED_AUTOLOCKED"
    assert r["session_forensic_capture"]["private_data_leaked"] is False
    assert r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V115 autonomy candidate review ---
def test_v115_default_absent_and_fixture_eligible_locked() -> None:
    d = generate_all_v115_reports_for_tests()["v115_autonomy_review_controller_report.json"]
    assert d["autonomy_eligibility_status"] in {"AUTONOMY_NOT_ELIGIBLE", "AUTONOMY_REPAIR_REQUIRED"}
    assert d["autonomous_trading_enabled"] is False
    ok = generate_all_v115_reports_for_tests(autonomy_approval=autonomy_approval(), prereq_override=True)["v115_autonomy_review_controller_report.json"]
    assert ok["autonomy_eligibility_status"] == "AUTONOMY_REVIEW_ELIGIBLE_LOCKED"
    assert ok["autonomous_trading_enabled"] is False
    fuzzy = generate_all_v115_reports_for_tests(autonomy_approval=autonomy_approval("bad"), prereq_override=True)["v115_autonomy_review_controller_report.json"]
    assert fuzzy["autonomy_review_controller_status"] == "FAIL_CLOSED_AUTONOMY_REPAIR_REQUIRED"
    assert_staged_safe(ok)


# --- safety / locks default across the whole bundle ---
def test_v106_to_v115_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v106_reports_for_tests,
        generate_all_v107_reports_for_tests,
        generate_all_v108_reports_for_tests,
        generate_all_v109_reports_for_tests,
        generate_all_v110_reports_for_tests,
        generate_all_v111_reports_for_tests,
        generate_all_v112_reports_for_tests,
        generate_all_v113_reports_for_tests,
        generate_all_v114_reports_for_tests,
        generate_all_v115_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
