from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from predator_mesh.report_runtime import generate_all_v175_reports_for_tests
from predator_mesh.report_runtime import generate_all_v176_reports_for_tests
from predator_mesh.report_runtime import generate_all_v177_reports_for_tests
from predator_mesh.report_runtime import generate_all_v178_reports_for_tests
from predator_mesh.report_runtime import generate_all_v179_reports_for_tests
from predator_mesh.report_runtime import generate_all_v180_reports_for_tests
from predator_mesh.report_runtime import generate_all_v181_reports_for_tests
from predator_mesh.report_runtime import generate_all_v182_reports_for_tests
from predator_mesh.report_runtime import generate_all_v183_reports_for_tests
from predator_mesh.report_runtime import generate_all_v184_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def operation_approval(phrase: str = sgc.CONTROLLED_OPERATION_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review controlled operation eligibility only", "scope": sgc.CONTROLLED_OPERATION_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def session_approval(phrase: str = sgc.CONTROLLED_SESSION_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "run one controlled live session canary via firewall", "scope": sgc.CONTROLLED_SESSION_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "strict_caps_acknowledgment": "strict caps", "per_order_fail_closed_acknowledgment": "per-order fail-closed checks",
        "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "session_auto_lock_acknowledgment": "immediate session auto-lock",
    }


def scale_approval(phrase: str = sgc.SCALE_STEP_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review scale step 1 only", "scope": sgc.SCALE_STEP_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def autonomy_approval(phrase: str = sgc.AUTONOMY_REVIEW_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review limited autonomy eligibility only", "scope": sgc.AUTONOMY_REVIEW_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


class FakeFirewall:
    """NON-broker firewall double. Never contacts a real broker; asserts no market orders."""

    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False, "session_id": order.get("session_id")}


# --- V175 controlled operation approval validator ---
def test_v175_default_absent_and_fixture_valid_no_submit() -> None:
    d = generate_all_v175_reports_for_tests()["v175_controlled_operation_approval_controller_report.json"]
    assert d["controlled_operation_approval_controller_status"] == "PARTIAL_CONTROLLED_OPERATION_APPROVAL_OR_LIVE_PROOF_ABSENT"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    ok = generate_all_v175_reports_for_tests(operation_approval=operation_approval(), session_approval=session_approval(), pilot_proof_override=True)["v175_controlled_operation_approval_controller_report.json"]
    assert ok["controlled_operation_approval_controller_status"] == "PASS_CONTROLLED_OPERATION_APPROVAL_VALID_NO_SUBMIT"
    assert ok["approval_files_written"] == 0
    fuzzy = generate_all_v175_reports_for_tests(operation_approval=operation_approval("bad"), session_approval=session_approval(), pilot_proof_override=True)["v175_controlled_operation_approval_controller_report.json"]
    assert fuzzy["controlled_operation_approval_controller_status"] == "FAIL_CLOSED_INVALID_CONTROLLED_OPERATION_OR_SESSION_APPROVAL"
    assert_staged_safe(ok)


# --- V176 live session final preflight ---
def test_v176_default_blocked_and_fixture_ready_no_submit() -> None:
    d = generate_all_v176_reports_for_tests()["v176_session_preflight_controller_report.json"]
    assert d["session_preflight_controller_status"] == "PARTIAL_LIVE_SESSION_PREFLIGHT_BLOCKED"
    ok = generate_all_v176_reports_for_tests(approval_ready_override=True)["v176_session_preflight_controller_report.json"]
    assert ok["session_preflight_controller_status"] == "PASS_LIVE_SESSION_PREFLIGHT_READY_NO_SUBMIT"
    assert ok["session_preflight_ready"] is True and ok["live_orders"] == 0
    assert_staged_safe(ok)


# --- V177 controlled operation session gate ---
def test_v177_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v177_reports_for_tests()["v177_controlled_session_gate_controller_report.json"]
    assert d["controlled_session_gate_controller_status"] == "PARTIAL_CONTROLLED_SESSION_NOT_ARMED"
    assert d["session_live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v177_reports_for_tests(session_approval=session_approval(), preflight_ready_override=True, pilot_proof_override=True, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, per_order_mode=True, firewall_adapter=FakeFirewall("v177-attempt-1"))["v177_controlled_session_gate_controller_report.json"]
    assert c["controlled_session_gate_controller_status"] == "PASS_CONTROLLED_SESSION_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v177-attempt-1"
    assert c["session_locked"] is True
    assert c["session_live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v177_missing_pilot_dry_mode_fuzzy_and_no_adapter_block() -> None:
    no_pilot = generate_all_v177_reports_for_tests(session_approval=session_approval(), preflight_ready_override=True, pilot_proof_override=False, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, per_order_mode=True, firewall_adapter=FakeFirewall("x"))["v177_controlled_session_gate_controller_report.json"]
    assert no_pilot["firewall_submit_invoked"] is False
    dry = generate_all_v177_reports_for_tests(session_approval=session_approval(), preflight_ready_override=True, pilot_proof_override=True, mode_live_override=False, live_submit_operator_enabled=True, caps_config_present=True, per_order_mode=True, firewall_adapter=FakeFirewall("x"))["v177_controlled_session_gate_controller_report.json"]
    assert dry["firewall_submit_invoked"] is False
    fuzzy = generate_all_v177_reports_for_tests(session_approval=session_approval("bad"), preflight_ready_override=True, pilot_proof_override=True, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, per_order_mode=True, firewall_adapter=FakeFirewall("x"))["v177_controlled_session_gate_controller_report.json"]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v177_reports_for_tests(session_approval=session_approval(), preflight_ready_override=True, pilot_proof_override=True, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, per_order_mode=True)["v177_controlled_session_gate_controller_report.json"]
    assert no_adapter["firewall_submit_invoked"] is False and no_adapter["session_live_orders"] == 0


# --- V178 controlled session reconcile ---
def test_v178_default_partial_and_override_classified() -> None:
    d = generate_all_v178_reports_for_tests()["v178_session_reconcile_controller_report.json"]
    assert d["session_reconcile_controller_status"] == "PARTIAL_NO_CONTROLLED_SESSION_TO_RECONCILE"
    assert d["session_state"] == "NO_ATTEMPT"
    r = generate_all_v178_reports_for_tests(v177_final_override={"controlled_session_gate_controller_status": "PASS_CONTROLLED_SESSION_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1}, session_state="FILLED")["v178_session_reconcile_controller_report.json"]
    assert r["session_reconcile_controller_status"] == "PASS_CONTROLLED_SESSION_STATE_CLASSIFIED_AUTOLOCKED"
    assert r["session_state"] == "FILLED" and r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V179 controlled session forensic ---
def test_v179_default_partial_and_override_reviewed() -> None:
    d = generate_all_v179_reports_for_tests()["v179_session_forensic_controller_report.json"]
    assert d["session_forensic_controller_status"] == "PARTIAL_NO_CONTROLLED_SESSION_TO_REVIEW"
    r = generate_all_v179_reports_for_tests(v178_final_override={"session_reconcile_controller_status": "PASS_CONTROLLED_SESSION_STATE_CLASSIFIED_AUTOLOCKED", "session_state": "FILLED"})["v179_session_forensic_controller_report.json"]
    assert r["session_forensic_controller_status"] == "PASS_CONTROLLED_SESSION_FORENSIC_REVIEWED"
    assert r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V180 session decision ---
def test_v180_default_stop_and_fixture_locked() -> None:
    d = generate_all_v180_reports_for_tests()["v180_session_decision_controller_report.json"]
    assert d["session_decision_controller_status"] == "PARTIAL_SESSION_DECISION_BLOCKED"
    assert d["session_decision"] == "STOP_NO_SESSION_PROOF"
    ok = generate_all_v180_reports_for_tests(session_proof_override=True)["v180_session_decision_controller_report.json"]
    assert ok["session_decision_controller_status"] == "PASS_SESSION_DECISION_LOCKED"
    assert ok["session_decision"] == "HOLD_CONTROLLED_OPERATION_LOCKED"
    assert_staged_safe(d)


# --- V181 scale review V2 ---
def test_v181_default_blocked_and_fixture_ready_no_scale() -> None:
    d = generate_all_v181_reports_for_tests()["v181_scale_review_controller_report.json"]
    assert d["scale_review_controller_status"] == "PARTIAL_SCALE_REVIEW_V2_BLOCKED"
    assert d["scale_recommendation"] == "SCALE_REVIEW_BLOCKED_NO_SESSION_PROOF"
    assert d["scale_applied"] is False and d["caps_changed"] is False
    ok = generate_all_v181_reports_for_tests(scale_approval=scale_approval(), session_evidence_override=True)["v181_scale_review_controller_report.json"]
    assert ok["scale_review_controller_status"] == "PASS_SCALE_REVIEW_V2_READY_LOCKED"
    assert ok["scale_recommendation"] == "SCALE_STEP_1_REVIEW_READY_LOCKED"
    fuzzy = generate_all_v181_reports_for_tests(scale_approval=scale_approval("bad"))["v181_scale_review_controller_report.json"]
    assert fuzzy["scale_review_controller_status"] == "FAIL_CLOSED_INVALID_SCALE_APPROVAL"
    assert_staged_safe(ok)


# --- V182 autonomy evidence review ---
def test_v182_default_blocked_and_fixture_ready_no_autonomy() -> None:
    d = generate_all_v182_reports_for_tests()["v182_autonomy_evidence_controller_report.json"]
    assert d["autonomy_evidence_controller_status"] == "PARTIAL_AUTONOMY_EVIDENCE_BLOCKED"
    assert d["autonomy_eligibility"] == "AUTONOMY_REVIEW_BLOCKED_NO_LIVE_SESSION_PROOF"
    assert d["autonomous_trading_enabled"] is False
    ok = generate_all_v182_reports_for_tests(autonomy_approval=autonomy_approval(), session_evidence_override=True)["v182_autonomy_evidence_controller_report.json"]
    assert ok["autonomy_evidence_controller_status"] == "PASS_AUTONOMY_EVIDENCE_REVIEW_READY_LOCKED"
    assert ok["autonomy_eligibility"] == "AUTONOMY_REVIEW_READY_LOCKED"
    assert ok["autonomous_trading_enabled"] is False
    fuzzy = generate_all_v182_reports_for_tests(autonomy_approval=autonomy_approval("bad"), session_evidence_override=True)["v182_autonomy_evidence_controller_report.json"]
    assert fuzzy["autonomy_evidence_controller_status"] == "FAIL_CLOSED_INVALID_AUTONOMY_REVIEW_APPROVAL"
    assert_staged_safe(ok)


# --- V183 limited autonomy dry-run policy ---
def test_v183_dryrun_policy_inert() -> None:
    d = generate_all_v183_reports_for_tests()["v183_limited_autonomy_dryrun_controller_report.json"]
    assert d["limited_autonomy_dryrun_controller_status"] == "PASS_LIMITED_AUTONOMY_DRYRUN_POLICY_LOCKED_INERT"
    assert d["autonomous_trading_enabled"] is False and d["live_orders"] == 0
    assert d["dry_run_inert"] is True
    assert_staged_safe(d)


# --- V184 production pilot lock V5 ---
def test_v184_lock_summary_default_await_session_approval() -> None:
    d = generate_all_v184_reports_for_tests()["v184_production_lock_controller_report.json"]
    assert d["production_lock_controller_status"] == "PASS_PRODUCTION_PILOT_LOCK_V5_SUMMARY_GENERATED"
    assert d["next_action_matrix_selection"] == "AWAIT_CONTROLLED_SESSION_APPROVAL"
    assert d["total_real_live_orders_submitted"] == 0
    assert d["autonomous_trading_enabled"] is False and d["scale_applied"] is False
    ready = generate_all_v184_reports_for_tests(approval_ready_override=True, session_done_override=True, session_reconciled_override=False)["v184_production_lock_controller_report.json"]
    assert ready["next_action_matrix_selection"] == "AWAIT_CONTROLLED_SESSION_RECONCILE"
    assert_staged_safe(d)


# --- safety / locks default across the whole bundle ---
def test_v175_to_v184_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v175_reports_for_tests,
        generate_all_v176_reports_for_tests,
        generate_all_v177_reports_for_tests,
        generate_all_v178_reports_for_tests,
        generate_all_v179_reports_for_tests,
        generate_all_v180_reports_for_tests,
        generate_all_v181_reports_for_tests,
        generate_all_v182_reports_for_tests,
        generate_all_v183_reports_for_tests,
        generate_all_v184_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
