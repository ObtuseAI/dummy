from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from predator_mesh.report_runtime import generate_all_v116_reports_for_tests
from predator_mesh.report_runtime import generate_all_v117_reports_for_tests
from predator_mesh.report_runtime import generate_all_v118_reports_for_tests
from predator_mesh.report_runtime import generate_all_v119_reports_for_tests
from predator_mesh.report_runtime import generate_all_v120_reports_for_tests
from predator_mesh.report_runtime import generate_all_v121_reports_for_tests
from predator_mesh.report_runtime import generate_all_v122_reports_for_tests
from predator_mesh.report_runtime import generate_all_v123_reports_for_tests
from predator_mesh.report_runtime import generate_all_v124_reports_for_tests
from predator_mesh.report_runtime import generate_all_v125_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def limited_session_approval(phrase: str = sgc.LIMITED_SESSION_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "prepare a limited autonomous session gate only", "scope": sgc.LIMITED_SESSION_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def dry_audit_approval(phrase: str = sgc.PRODUCTION_DRY_AUDIT_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "run a production dry audit only", "scope": sgc.PRODUCTION_DRY_AUDIT_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def pilot_approval(phrase: str = sgc.CONTROLLED_PILOT_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "run one controlled production pilot via firewall", "scope": sgc.CONTROLLED_PILOT_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "strict_caps_acknowledgment": "strict caps", "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "per_order_fail_closed_acknowledgment": "per-order fail-closed checks", "pilot_auto_lock_acknowledgment": "immediate pilot auto-lock",
    }


def repeat_approval(phrase: str = sgc.REPEAT_PILOT_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review a repeat controlled production pilot only", "scope": sgc.REPEAT_PILOT_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def scale_approval(phrase: str = sgc.SCALE_STEP_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review scale step 1 only", "scope": sgc.SCALE_STEP_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


class FakeFirewall:
    """NON-broker firewall double. Never contacts a real broker; asserts no market orders."""

    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False, "pilot_id": order.get("pilot_id")}


# --- V116 autonomous trade/abstain/lock policy ---
def test_v116_autonomy_policy_locked_no_autonomy() -> None:
    d = generate_all_v116_reports_for_tests()["v116_autonomy_policy_controller_report.json"]
    assert d["autonomy_policy_controller_status"] == "PASS_AUTONOMY_POLICY_LOCKED"
    assert d["default_policy_state"] == "TRADE_FORBIDDEN_MISSING_APPROVAL"
    assert d["autonomous_trading_enabled"] is False
    assert len(d["policy_states"]) == 5
    assert_staged_safe(d)


# --- V117 limited autonomous session gate ---
def test_v117_default_absent_and_fixture_prepared_locked() -> None:
    d = generate_all_v117_reports_for_tests()["v117_limited_session_gate_controller_report.json"]
    assert d["limited_session_gate_controller_status"] == "PARTIAL_LIMITED_SESSION_APPROVAL_ABSENT"
    assert d["autonomous_submit_enabled"] is False and d["live_orders"] == 0
    ok = generate_all_v117_reports_for_tests(session_approval=limited_session_approval())["v117_limited_session_gate_controller_report.json"]
    assert ok["limited_session_gate_controller_status"] == "PASS_LIMITED_SESSION_GATE_PREPARED_LOCKED_NO_AUTO_SUBMIT"
    assert ok["autonomous_submit_enabled"] is False and ok["live_orders"] == 0 and ok["gate_locked"] is True
    fuzzy = generate_all_v117_reports_for_tests(session_approval=limited_session_approval("bad phrase"))["v117_limited_session_gate_controller_report.json"]
    assert fuzzy["limited_session_gate_controller_status"] == "FAIL_CLOSED_INVALID_LIMITED_SESSION_APPROVAL"
    assert_staged_safe(ok)


# --- V118 production dry audit ---
def test_v118_dry_audit_locked_no_broker_contact() -> None:
    d = generate_all_v118_reports_for_tests()["v118_production_dry_audit_controller_report.json"]
    assert d["production_dry_audit_controller_status"] == "PASS_DRY_AUDIT_LOCKED"
    assert d["broker_contacted"] is False and d["live_orders"] == 0
    ok = generate_all_v118_reports_for_tests(dry_audit_approval=dry_audit_approval())["v118_production_dry_audit_controller_report.json"]
    assert ok["production_dry_audit_controller_status"] == "PASS_DRY_AUDIT_APPROVED_LOCKED"
    fuzzy = generate_all_v118_reports_for_tests(dry_audit_approval=dry_audit_approval("bad"))["v118_production_dry_audit_controller_report.json"]
    assert fuzzy["production_dry_audit_controller_status"] == "FAIL_CLOSED_INVALID_DRY_AUDIT_APPROVAL"
    assert_staged_safe(d)


# --- V119 controlled production pilot gate ---
def test_v119_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v119_reports_for_tests()["v119_pilot_gate_controller_report.json"]
    assert d["pilot_gate_controller_status"] == "PARTIAL_PRODUCTION_PILOT_NOT_ARMED"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v119_reports_for_tests(pilot_approval=pilot_approval(), dry_audit_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v119-attempt-1"))["v119_pilot_gate_controller_report.json"]
    assert c["pilot_gate_controller_status"] == "PASS_PRODUCTION_PILOT_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v119-attempt-1"
    assert c["pilot_locked"] is True
    assert c["live_orders"] == 0
    assert c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False
    assert c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v119_fuzzy_and_no_adapter_block() -> None:
    fuzzy = generate_all_v119_reports_for_tests(pilot_approval=pilot_approval("bad"), dry_audit_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v119_pilot_gate_controller_report.json"]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v119_reports_for_tests(pilot_approval=pilot_approval(), dry_audit_ready_override=True, live_submit_operator_enabled=True, caps_config_present=True)["v119_pilot_gate_controller_report.json"]
    assert no_adapter["firewall_submit_invoked"] is False
    assert no_adapter["live_orders"] == 0


# --- V120 production pilot forensic review ---
def test_v120_default_partial_and_override_reviewed() -> None:
    d = generate_all_v120_reports_for_tests()["v120_pilot_forensic_controller_report.json"]
    assert d["pilot_forensic_controller_status"] == "PARTIAL_NO_PRODUCTION_PILOT_TO_REVIEW"
    r = generate_all_v120_reports_for_tests(v119_final_override={"pilot_gate_controller_status": "PASS_PRODUCTION_PILOT_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1})["v120_pilot_forensic_controller_report.json"]
    assert r["pilot_forensic_controller_status"] == "PASS_PRODUCTION_PILOT_REVIEWED_AUTOLOCKED"
    assert r["pilot_forensic_capture"]["private_data_leaked"] is False
    assert r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V121 repeat production pilot gate ---
def test_v121_default_absent_and_fixture_eligible_locked() -> None:
    d = generate_all_v121_reports_for_tests()["v121_repeat_pilot_gate_controller_report.json"]
    assert d["repeat_pilot_gate_controller_status"] == "PARTIAL_REPEAT_PILOT_APPROVAL_OR_FIRST_PILOT_PROOF_ABSENT"
    assert d["live_orders"] == 0 and d["auto_repeat_enabled"] is False
    ok = generate_all_v121_reports_for_tests(repeat_approval=repeat_approval(), first_pilot_override=True)["v121_repeat_pilot_gate_controller_report.json"]
    assert ok["repeat_pilot_gate_controller_status"] == "PASS_REPEAT_PILOT_REVIEW_ELIGIBLE_LOCKED"
    assert ok["repeat_pilot_recommendation"] == "REPEAT_PILOT_REVIEW_READY"
    fuzzy = generate_all_v121_reports_for_tests(repeat_approval=repeat_approval("bad"), first_pilot_override=True)["v121_repeat_pilot_gate_controller_report.json"]
    assert fuzzy["repeat_pilot_gate_controller_status"] == "FAIL_CLOSED_INVALID_REPEAT_PILOT_APPROVAL"
    assert_staged_safe(ok)


# --- V122 production risk & stop policy ---
def test_v122_risk_stop_policies_locked_no_order() -> None:
    d = generate_all_v122_reports_for_tests()["v122_risk_stop_policy_controller_report.json"]
    assert d["risk_stop_policy_controller_status"] == "PASS_RISK_STOP_POLICIES_GENERATED_AND_LOCKED"
    assert d["session_kill_switch_status"] == "PASS_SESSION_KILL_SWITCH_ARMED"
    assert d["caps_modified"] is False and d["live_orders"] == 0
    assert_staged_safe(d)


# --- V123 scale-step 1 review lock ---
def test_v123_scale_review_no_caps_change() -> None:
    d = generate_all_v123_reports_for_tests()["v123_scale_review_controller_report.json"]
    assert d["scale_review_controller_status"] == "PASS_SCALE_REVIEWED_NO_SCALE_APPLIED"
    assert d["scale_recommendation"] == "NO_SCALE"
    assert d["caps_changed"] is False and d["scale_applied"] is False
    ready = generate_all_v123_reports_for_tests(scale_approval=scale_approval(), pilot_evidence_override=True, production_ready_override=True)["v123_scale_review_controller_report.json"]
    assert ready["scale_recommendation"] == "SCALE_STEP_1_REVIEW_READY"
    assert ready["caps_changed"] is False
    fuzzy = generate_all_v123_reports_for_tests(scale_approval=scale_approval("bad"))["v123_scale_review_controller_report.json"]
    assert fuzzy["scale_review_controller_status"] == "FAIL_CLOSED_INVALID_SCALE_APPROVAL"
    assert_staged_safe(ready)


# --- V124 controlled operation gate ---
def test_v124_controlled_operation_ready_locked_no_autonomy() -> None:
    d = generate_all_v124_reports_for_tests()["v124_controlled_operation_gate_controller_report.json"]
    assert d["controlled_operation_gate_controller_status"] == "PASS_CONTROLLED_OPERATION_GATE_READY_LOCKED"
    assert d["autonomous_trading_enabled"] is False
    assert d["per_order_approval_required"] is True
    assert d["no_auto_submit_proof_status"] == "PASS_NO_AUTO_SUBMIT"
    assert_staged_safe(d)


# --- V125 production lock & next-phase audit ---
def test_v125_production_lock_summary_default_await_pilot() -> None:
    d = generate_all_v125_reports_for_tests()["v125_production_lock_controller_report.json"]
    assert d["production_lock_controller_status"] == "PASS_PRODUCTION_LOCK_SUMMARY_GENERATED"
    assert d["next_action_matrix_selection"] == "AWAIT_CONTROLLED_PILOT_APPROVAL"
    assert d["autonomous_trading_enabled"] is False and d["scale_applied"] is False
    assert d["new_order_placed"] is False
    ready = generate_all_v125_reports_for_tests(pilot_override="PASS_PRODUCTION_PILOT_SUBMITTED_AUTOLOCKED", repeat_override="PASS_REPEAT_PILOT_REVIEW_ELIGIBLE_LOCKED", scale_override="SCALE_STEP_1_REVIEW_READY")["v125_production_lock_controller_report.json"]
    assert ready["next_action_matrix_selection"] == "CONTROLLED_OPERATION_READY_LOCKED"
    assert_staged_safe(d)


# --- safety / locks default across the whole bundle ---
def test_v116_to_v125_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v116_reports_for_tests,
        generate_all_v117_reports_for_tests,
        generate_all_v118_reports_for_tests,
        generate_all_v119_reports_for_tests,
        generate_all_v120_reports_for_tests,
        generate_all_v121_reports_for_tests,
        generate_all_v122_reports_for_tests,
        generate_all_v123_reports_for_tests,
        generate_all_v124_reports_for_tests,
        generate_all_v125_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
