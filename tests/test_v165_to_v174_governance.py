from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from predator_mesh.report_runtime import generate_all_v165_reports_for_tests
from predator_mesh.report_runtime import generate_all_v166_reports_for_tests
from predator_mesh.report_runtime import generate_all_v167_reports_for_tests
from predator_mesh.report_runtime import generate_all_v168_reports_for_tests
from predator_mesh.report_runtime import generate_all_v169_reports_for_tests
from predator_mesh.report_runtime import generate_all_v170_reports_for_tests
from predator_mesh.report_runtime import generate_all_v171_reports_for_tests
from predator_mesh.report_runtime import generate_all_v172_reports_for_tests
from predator_mesh.report_runtime import generate_all_v173_reports_for_tests
from predator_mesh.report_runtime import generate_all_v174_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def repeat_approval(phrase: str = sgc.REPEAT_PILOT_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review a repeat controlled production pilot only", "scope": sgc.REPEAT_PILOT_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def scale_approval(phrase: str = sgc.SCALE_STEP_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review scale step 1 only", "scope": sgc.SCALE_STEP_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def operation_approval(phrase: str = sgc.CONTROLLED_OPERATION_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review controlled operation eligibility only", "scope": sgc.CONTROLLED_OPERATION_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


class FakeFirewall:
    """NON-broker firewall double. Never contacts a real broker; asserts no market orders."""

    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False, "repeat_pilot_id": order.get("repeat_pilot_id")}


# --- V165 repeat authority binder ---
def test_v165_default_blocked_and_fixture_bound() -> None:
    d = generate_all_v165_reports_for_tests()["v165_repeat_authority_binder_controller_report.json"]
    assert d["repeat_authority_binder_controller_status"] == "PARTIAL_REPEAT_AUTHORITY_BLOCKED_NO_FIRST_PILOT_PROOF"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    ok = generate_all_v165_reports_for_tests(repeat_approval=repeat_approval(), first_pilot_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v165_repeat_authority_binder_controller_report.json"]
    assert ok["repeat_authority_binder_controller_status"] == "PASS_REPEAT_AUTHORITY_BOUND_NO_SUBMIT"
    assert ok["authority_bound"] is True and ok["approval_files_written"] == 0
    fuzzy = generate_all_v165_reports_for_tests(repeat_approval=repeat_approval("bad"), first_pilot_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v165_repeat_authority_binder_controller_report.json"]
    assert fuzzy["repeat_authority_binder_controller_status"] == "FAIL_CLOSED_INVALID_REPEAT_APPROVAL"
    assert_staged_safe(ok)


# --- V166 repeat preflight ---
def test_v166_default_blocked_and_fixture_ready_no_submit() -> None:
    d = generate_all_v166_reports_for_tests()["v166_repeat_preflight_controller_report.json"]
    assert d["repeat_preflight_controller_status"] == "PARTIAL_REPEAT_PREFLIGHT_BLOCKED"
    ok = generate_all_v166_reports_for_tests(binder_ready_override=True)["v166_repeat_preflight_controller_report.json"]
    assert ok["repeat_preflight_controller_status"] == "PASS_REPEAT_PREFLIGHT_READY_NO_SUBMIT"
    assert ok["repeat_preflight_ready"] is True and ok["live_orders"] == 0
    assert_staged_safe(ok)


# --- V167 repeat pilot fire gate ---
def test_v167_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v167_reports_for_tests()["v167_repeat_pilot_gate_controller_report.json"]
    assert d["repeat_pilot_gate_controller_status"] == "PARTIAL_REPEAT_PILOT_NOT_ARMED"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v167_reports_for_tests(repeat_approval=repeat_approval(), preflight_ready_override=True, first_pilot_override=True, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v167-attempt-1"))["v167_repeat_pilot_gate_controller_report.json"]
    assert c["repeat_pilot_gate_controller_status"] == "PASS_REPEAT_PILOT_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v167-attempt-1"
    assert c["repeat_pilot_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v167_missing_first_pilot_dry_mode_fuzzy_and_no_adapter_block() -> None:
    no_first = generate_all_v167_reports_for_tests(repeat_approval=repeat_approval(), preflight_ready_override=True, first_pilot_override=False, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v167_repeat_pilot_gate_controller_report.json"]
    assert no_first["firewall_submit_invoked"] is False
    dry = generate_all_v167_reports_for_tests(repeat_approval=repeat_approval(), preflight_ready_override=True, first_pilot_override=True, mode_live_override=False, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v167_repeat_pilot_gate_controller_report.json"]
    assert dry["firewall_submit_invoked"] is False
    fuzzy = generate_all_v167_reports_for_tests(repeat_approval=repeat_approval("bad"), preflight_ready_override=True, first_pilot_override=True, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v167_repeat_pilot_gate_controller_report.json"]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v167_reports_for_tests(repeat_approval=repeat_approval(), preflight_ready_override=True, first_pilot_override=True, mode_live_override=True, live_submit_operator_enabled=True, caps_config_present=True)["v167_repeat_pilot_gate_controller_report.json"]
    assert no_adapter["firewall_submit_invoked"] is False and no_adapter["live_orders"] == 0


# --- V168 repeat reconcile ---
def test_v168_default_partial_and_override_classified() -> None:
    d = generate_all_v168_reports_for_tests()["v168_repeat_reconcile_controller_report.json"]
    assert d["repeat_reconcile_controller_status"] == "PARTIAL_NO_REPEAT_PILOT_TO_RECONCILE"
    assert d["order_state"] == "NO_ATTEMPT"
    r = generate_all_v168_reports_for_tests(v167_final_override={"repeat_pilot_gate_controller_status": "PASS_REPEAT_PILOT_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1}, outcome_state="FILLED")["v168_repeat_reconcile_controller_report.json"]
    assert r["repeat_reconcile_controller_status"] == "PASS_REPEAT_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
    assert r["order_state"] == "FILLED" and r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V169 repeat forensic ---
def test_v169_default_partial_and_override_reviewed() -> None:
    d = generate_all_v169_reports_for_tests()["v169_repeat_forensic_controller_report.json"]
    assert d["repeat_forensic_controller_status"] == "PARTIAL_NO_REPEAT_PILOT_TO_REVIEW"
    r = generate_all_v169_reports_for_tests(v168_final_override={"repeat_reconcile_controller_status": "PASS_REPEAT_PILOT_STATE_CLASSIFIED_AUTOLOCKED", "order_state": "FILLED"})["v169_repeat_forensic_controller_report.json"]
    assert r["repeat_forensic_controller_status"] == "PASS_REPEAT_PILOT_FORENSIC_REVIEWED"
    assert r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V170 pilot pair audit ---
def test_v170_default_stop_and_fixture_audited() -> None:
    d = generate_all_v170_reports_for_tests()["v170_pilot_pair_audit_controller_report.json"]
    assert d["pilot_pair_audit_controller_status"] == "PARTIAL_PILOT_PAIR_PROOF_ABSENT"
    assert d["pair_decision"] == "STOP_NO_PILOT_PAIR_PROOF"
    ok = generate_all_v170_reports_for_tests(first_pilot_override=True, repeat_pilot_override=True)["v170_pilot_pair_audit_controller_report.json"]
    assert ok["pilot_pair_audit_controller_status"] == "PASS_PILOT_PAIR_AUDITED_LOCKED"
    assert ok["pair_decision"] == "SCALE_REVIEW_ELIGIBLE_LOCKED"
    assert_staged_safe(d)


# --- V171 scale evidence validator ---
def test_v171_default_blocked_and_fixture_ready_no_scale() -> None:
    d = generate_all_v171_reports_for_tests()["v171_scale_evidence_controller_report.json"]
    assert d["scale_evidence_controller_status"] == "PARTIAL_SCALE_EVIDENCE_BLOCKED"
    assert d["scale_recommendation"] == "SCALE_REVIEW_BLOCKED_NO_LIVE_PROOF"
    assert d["scale_applied"] is False and d["caps_changed"] is False
    ok = generate_all_v171_reports_for_tests(scale_approval=scale_approval(), pair_evidence_override=True)["v171_scale_evidence_controller_report.json"]
    assert ok["scale_evidence_controller_status"] == "PASS_SCALE_EVIDENCE_REVIEW_READY_LOCKED"
    assert ok["scale_recommendation"] == "SCALE_STEP_1_REVIEW_READY_LOCKED"
    assert ok["scale_applied"] is False
    fuzzy = generate_all_v171_reports_for_tests(scale_approval=scale_approval("bad"))["v171_scale_evidence_controller_report.json"]
    assert fuzzy["scale_evidence_controller_status"] == "FAIL_CLOSED_INVALID_SCALE_APPROVAL"
    assert_staged_safe(ok)


# --- V172 controlled operation quorum ---
def test_v172_default_blocked_and_fixture_ready() -> None:
    d = generate_all_v172_reports_for_tests()["v172_controlled_operation_quorum_controller_report.json"]
    assert d["controlled_operation_quorum_controller_status"] == "PARTIAL_CONTROLLED_OPERATION_QUORUM_BLOCKED"
    assert d["autonomous_trading_enabled"] is False
    ok = generate_all_v172_reports_for_tests(operation_approval=operation_approval(), pair_evidence_override=True)["v172_controlled_operation_quorum_controller_report.json"]
    assert ok["controlled_operation_quorum_controller_status"] == "PASS_CONTROLLED_OPERATION_QUORUM_READY_LOCKED"
    assert ok["quorum_ready"] is True
    fuzzy = generate_all_v172_reports_for_tests(operation_approval=operation_approval("bad"), pair_evidence_override=True)["v172_controlled_operation_quorum_controller_report.json"]
    assert fuzzy["controlled_operation_quorum_controller_status"] == "FAIL_CLOSED_INVALID_CONTROLLED_OPERATION_APPROVAL"
    assert_staged_safe(ok)


# --- V173 controlled operation dry session ---
def test_v173_dry_session_inert() -> None:
    d = generate_all_v173_reports_for_tests()["v173_dry_session_controller_report.json"]
    assert d["dry_session_controller_status"] == "PASS_CONTROLLED_OPERATION_DRY_SESSION_READY_INERT"
    assert d["broker_contacted"] is False and d["dry_session_inert"] is True
    assert d["live_orders"] == 0
    assert_staged_safe(d)


# --- V174 controlled operation lock V4 ---
def test_v174_lock_summary_default_await_first_pilot() -> None:
    d = generate_all_v174_reports_for_tests()["v174_controlled_operation_lock_controller_report.json"]
    assert d["controlled_operation_lock_controller_status"] == "PASS_CONTROLLED_OPERATION_LOCK_V4_SUMMARY_GENERATED"
    assert d["next_action_matrix_selection"] == "AWAIT_FIRST_REAL_PILOT_PROOF"
    assert d["total_real_live_orders_submitted"] == 0
    assert d["autonomous_trading_enabled"] is False and d["scale_applied"] is False
    ready = generate_all_v174_reports_for_tests(first_pilot_override=True)["v174_controlled_operation_lock_controller_report.json"]
    assert ready["next_action_matrix_selection"] == "AWAIT_REPEAT_PILOT_APPROVAL"
    assert_staged_safe(d)


# --- safety / locks default across the whole bundle ---
def test_v165_to_v174_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v165_reports_for_tests,
        generate_all_v166_reports_for_tests,
        generate_all_v167_reports_for_tests,
        generate_all_v168_reports_for_tests,
        generate_all_v169_reports_for_tests,
        generate_all_v170_reports_for_tests,
        generate_all_v171_reports_for_tests,
        generate_all_v172_reports_for_tests,
        generate_all_v173_reports_for_tests,
        generate_all_v174_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
