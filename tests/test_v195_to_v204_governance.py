from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from archive.report_scripts.generate_v195_reports import generate_all_v195_reports_for_tests
from archive.report_scripts.generate_v196_reports import generate_all_v196_reports_for_tests
from archive.report_scripts.generate_v197_reports import generate_all_v197_reports_for_tests
from archive.report_scripts.generate_v198_reports import generate_all_v198_reports_for_tests
from archive.report_scripts.generate_v199_reports import generate_all_v199_reports_for_tests
from archive.report_scripts.generate_v200_reports import generate_all_v200_reports_for_tests
from archive.report_scripts.generate_v201_reports import generate_all_v201_reports_for_tests
from archive.report_scripts.generate_v202_reports import generate_all_v202_reports_for_tests
from archive.report_scripts.generate_v203_reports import generate_all_v203_reports_for_tests
from archive.report_scripts.generate_v204_reports import generate_all_v204_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe


def pilot_approval(phrase: str = sgc.CONTROLLED_PILOT_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "run one controlled production pilot via firewall", "scope": sgc.CONTROLLED_PILOT_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "strict_caps_acknowledgment": "strict caps", "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "per_order_fail_closed_acknowledgment": "per-order fail-closed checks", "pilot_auto_lock_acknowledgment": "immediate pilot auto-lock",
    }


def session_approval(phrase: str = sgc.CONTROLLED_SESSION_PHRASE) -> dict:
    return {
        "exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z",
        "reason": "run one controlled live session canary via firewall", "scope": sgc.CONTROLLED_SESSION_SCOPE,
        "expiration": "2026-07-06T21:00:00Z", "no_market_order_acknowledgment": "no market order",
        "strict_caps_acknowledgment": "strict caps", "per_order_fail_closed_acknowledgment": "per-order fail-closed checks",
        "live_submit_operator_enabled_acknowledgment": "live-submit already operator-enabled",
        "session_auto_lock_acknowledgment": "immediate session auto-lock",
    }


def broker_readonly_approval(phrase: str = sgc.BROKER_READONLY_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "broker read-only verification only", "scope": sgc.BROKER_READONLY_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def scale_approval(phrase: str = sgc.SCALE_STEP_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review scale step 1 only", "scope": sgc.SCALE_STEP_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def autonomy_approval(phrase: str = sgc.AUTONOMY_REVIEW_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review limited autonomy eligibility only", "scope": sgc.AUTONOMY_REVIEW_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


class FakeFirewall:
    def __init__(self, aid):
        self.aid = aid

    def submit(self, order):
        assert order["is_market_order"] is False
        return {"order_attempt_id": self.aid, "accepted": True, "real_broker_contacted": False, "market_order": False, "session_id": order.get("session_id")}


class FakeReadOnlyAdapter:
    def read_only_verify(self):
        return {"real_broker_contacted": False, "submit_call_made": False, "cancel_call_made": False, "account_status": "REDACTED"}


# --- V195 activation binder ---
def test_v195_default_incomplete_and_fixture_bound() -> None:
    d = generate_all_v195_reports_for_tests()["v195_activation_binder_controller_report.json"]
    assert d["activation_binder_controller_status"] == "PARTIAL_FIRST_LIVE_PROOF_AUTHORITY_INCOMPLETE"
    ok = generate_all_v195_reports_for_tests(pilot_approval=pilot_approval(), session_approval=session_approval(), broker_readonly_approval=broker_readonly_approval(), live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v195_activation_binder_controller_report.json"]
    assert ok["activation_binder_controller_status"] == "PASS_FIRST_LIVE_PROOF_AUTHORITY_BOUND_NO_SUBMIT"
    assert ok["approval_files_written"] == 0
    fuzzy = generate_all_v195_reports_for_tests(pilot_approval=pilot_approval("bad"), live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v195_activation_binder_controller_report.json"]
    assert fuzzy["activation_binder_controller_status"] == "FAIL_CLOSED_INVALID_ACTIVATION_APPROVAL"
    assert_staged_safe(ok)


# --- V196 config/caps immutable quorum ---
def test_v196_default_blocked_and_fixture_ready_immutable() -> None:
    d = generate_all_v196_reports_for_tests()["v196_config_quorum_controller_report.json"]
    assert d["config_quorum_controller_status"] == "PARTIAL_LIVE_CONFIG_CAPS_QUORUM_BLOCKED"
    assert d["live_submit_changed"] is False and d["caps_changed"] is False
    ok = generate_all_v196_reports_for_tests(live_submit_operator_enabled=True, caps_config_present=True)["v196_config_quorum_controller_report.json"]
    assert ok["config_quorum_controller_status"] == "PASS_LIVE_CONFIG_CAPS_QUORUM_READY_IMMUTABLE"
    assert ok["live_submit_hash_before"] == ok["live_submit_hash_after"]
    assert_staged_safe(ok)


# --- V197 firewall/broker verification V2 ---
def test_v197_default_absent_and_fixture_verified() -> None:
    d = generate_all_v197_reports_for_tests()["v197_firewall_broker_controller_report.json"]
    assert d["firewall_broker_controller_status"] == "PARTIAL_FIREWALL_OR_BROKER_READONLY_AUTHORITY_ABSENT"
    assert d["real_broker_contacted"] is False
    ok = generate_all_v197_reports_for_tests(firewall_adapter=FakeFirewall("x"), broker_readonly_approval=broker_readonly_approval(), readonly_adapter=FakeReadOnlyAdapter())["v197_firewall_broker_controller_report.json"]
    assert ok["firewall_broker_controller_status"] == "PASS_FIREWALL_AND_BROKER_READONLY_VERIFIED_NO_SUBMIT_CANCEL"
    assert ok["real_broker_contacted"] is False and ok["submit_call_made"] is False
    fuzzy = generate_all_v197_reports_for_tests(firewall_adapter=FakeFirewall("x"), broker_readonly_approval=broker_readonly_approval("bad"), readonly_adapter=FakeReadOnlyAdapter())["v197_firewall_broker_controller_report.json"]
    assert fuzzy["firewall_broker_controller_status"] == "FAIL_CLOSED_INVALID_BROKER_READONLY_APPROVAL"
    assert_staged_safe(ok)


# --- V198 first live-proof final quorum ---
def test_v198_default_blocked_and_fixture_ready_no_submit() -> None:
    d = generate_all_v198_reports_for_tests()["v198_final_quorum_controller_report.json"]
    assert d["final_quorum_controller_status"] == "PARTIAL_FIRST_LIVE_PROOF_QUORUM_BLOCKED"
    assert d["proof_target"] == "BLOCKED_NO_AUTHORITY"
    ok = generate_all_v198_reports_for_tests(approval_ready_override=True, config_ready_override=True, firewall_ready_override=True)["v198_final_quorum_controller_report.json"]
    assert ok["final_quorum_controller_status"] == "PASS_FIRST_LIVE_PROOF_QUORUM_READY_NO_SUBMIT"
    assert ok["proof_target"] == "FIRST_REAL_PILOT_PROOF" and ok["live_orders"] == 0
    assert_staged_safe(ok)


# --- V199 first live-proof fire gate ---
def test_v199_default_not_armed_and_full_auth_double() -> None:
    d = generate_all_v199_reports_for_tests()["v199_first_live_proof_gate_controller_report.json"]
    assert d["first_live_proof_gate_controller_status"] == "PARTIAL_FIRST_LIVE_PROOF_NOT_ARMED"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    c = generate_all_v199_reports_for_tests(proof_approval=pilot_approval(), quorum_ready_override=True, mode_live_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF", live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("v199-attempt-1"))["v199_first_live_proof_gate_controller_report.json"]
    assert c["first_live_proof_gate_controller_status"] == "PASS_FIRST_LIVE_PROOF_SUBMITTED_AUTOLOCKED"
    assert c["order_attempt_id"] == "v199-attempt-1"
    assert c["proof_locked"] is True
    assert c["live_orders"] == 0 and c["real_live_orders_submitted_count"] == 0
    assert c["real_broker_contacted"] is False and c["market_order_submitted"] is False
    assert_staged_safe(c)


def test_v199_dry_mode_missing_quorum_fuzzy_and_no_adapter_block() -> None:
    dry = generate_all_v199_reports_for_tests(proof_approval=pilot_approval(), quorum_ready_override=True, mode_live_override=False, proof_target_override="FIRST_REAL_PILOT_PROOF", live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v199_first_live_proof_gate_controller_report.json"]
    assert dry["firewall_submit_invoked"] is False
    no_quorum = generate_all_v199_reports_for_tests(proof_approval=pilot_approval(), quorum_ready_override=False, mode_live_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF", live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v199_first_live_proof_gate_controller_report.json"]
    assert no_quorum["firewall_submit_invoked"] is False
    fuzzy = generate_all_v199_reports_for_tests(proof_approval=pilot_approval("bad"), quorum_ready_override=True, mode_live_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF", live_submit_operator_enabled=True, caps_config_present=True, firewall_adapter=FakeFirewall("x"))["v199_first_live_proof_gate_controller_report.json"]
    assert fuzzy["firewall_submit_invoked"] is False
    no_adapter = generate_all_v199_reports_for_tests(proof_approval=pilot_approval(), quorum_ready_override=True, mode_live_override=True, proof_target_override="FIRST_REAL_PILOT_PROOF", live_submit_operator_enabled=True, caps_config_present=True)["v199_first_live_proof_gate_controller_report.json"]
    assert no_adapter["firewall_submit_invoked"] is False and no_adapter["live_orders"] == 0


# --- V200 first live-proof reconcile ---
def test_v200_default_partial_and_override_classified() -> None:
    d = generate_all_v200_reports_for_tests()["v200_reconcile_controller_report.json"]
    assert d["reconcile_controller_status"] == "PARTIAL_NO_FIRST_LIVE_PROOF_TO_RECONCILE"
    assert d["order_state"] == "NO_ATTEMPT"
    r = generate_all_v200_reports_for_tests(v199_final_override={"first_live_proof_gate_controller_status": "PASS_FIRST_LIVE_PROOF_SUBMITTED_AUTOLOCKED", "simulated_order_submits_count": 1, "proof_target": "FIRST_REAL_PILOT_PROOF"}, outcome_state="FILLED")["v200_reconcile_controller_report.json"]
    assert r["reconcile_controller_status"] == "PASS_FIRST_LIVE_PROOF_STATE_CLASSIFIED_AUTOLOCKED"
    assert r["order_state"] == "FILLED" and r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V201 first live-proof forensic ---
def test_v201_default_partial_and_override_reviewed() -> None:
    d = generate_all_v201_reports_for_tests()["v201_forensic_controller_report.json"]
    assert d["forensic_controller_status"] == "PARTIAL_NO_FIRST_LIVE_PROOF_TO_REVIEW"
    r = generate_all_v201_reports_for_tests(v200_final_override={"reconcile_controller_status": "PASS_FIRST_LIVE_PROOF_STATE_CLASSIFIED_AUTOLOCKED", "order_state": "FILLED", "proof_target": "FIRST_REAL_PILOT_PROOF"})["v201_forensic_controller_report.json"]
    assert r["forensic_controller_status"] == "PASS_FIRST_LIVE_PROOF_FORENSIC_REVIEWED"
    assert r["new_order_placed"] is False
    assert_staged_safe(r)


# --- V202 scale/autonomy evidence refresh ---
def test_v202_default_blocked_and_fixture_ready_no_scale_no_autonomy() -> None:
    d = generate_all_v202_reports_for_tests()["v202_evidence_refresh_controller_report.json"]
    assert d["evidence_refresh_controller_status"] == "PARTIAL_SCALE_AND_AUTONOMY_EVIDENCE_BLOCKED"
    assert d["scale_recommendation"] == "SCALE_BLOCKED_NO_LIVE_PROOF"
    assert d["autonomy_recommendation"] == "AUTONOMY_BLOCKED_NO_LIVE_PROOF"
    assert d["scale_applied"] is False and d["autonomous_trading_enabled"] is False
    ok = generate_all_v202_reports_for_tests(scale_approval=scale_approval(), autonomy_approval=autonomy_approval(), live_proof_override=True)["v202_evidence_refresh_controller_report.json"]
    assert ok["evidence_refresh_controller_status"] == "PASS_SCALE_AND_AUTONOMY_EVIDENCE_REVIEW_READY_LOCKED"
    assert ok["scale_recommendation"] == "SCALE_REVIEW_READY_LOCKED"
    assert ok["autonomy_recommendation"] == "AUTONOMY_REVIEW_READY_LOCKED"
    assert ok["scale_applied"] is False and ok["autonomous_trading_enabled"] is False
    assert_staged_safe(ok)


# --- V203 controlled operation status gate V7 ---
def test_v203_default_blocked_and_fixture_review_ready() -> None:
    d = generate_all_v203_reports_for_tests()["v203_controlled_operation_status_controller_report.json"]
    assert d["controlled_operation_status"] == "CONTROLLED_OPERATION_BLOCKED_NO_LIVE_PROOF"
    assert d["autonomous_trading_enabled"] is False
    ok = generate_all_v203_reports_for_tests(live_proof_override=True)["v203_controlled_operation_status_controller_report.json"]
    assert ok["controlled_operation_status"] == "CONTROLLED_OPERATION_REVIEW_READY_LOCKED"
    per_order = generate_all_v203_reports_for_tests(live_proof_override=True, per_order_ready_override=True)["v203_controlled_operation_status_controller_report.json"]
    assert per_order["controlled_operation_status"] == "CONTROLLED_OPERATION_READY_PER_ORDER_ONLY_LOCKED"
    assert_staged_safe(ok)


# --- V204 production lock V7 ---
def test_v204_lock_summary_default_await_approval_files() -> None:
    d = generate_all_v204_reports_for_tests()["v204_production_lock_controller_report.json"]
    assert d["production_lock_controller_status"] == "PASS_PRODUCTION_LOCK_V7_SUMMARY_GENERATED"
    assert d["next_action_matrix_selection"] == "AWAIT_OPERATOR_APPROVAL_FILES"
    assert d["total_real_live_orders_submitted"] == 0
    assert d["autonomous_trading_enabled"] is False and d["scale_applied"] is False
    ready = generate_all_v204_reports_for_tests(binder_ready_override=True, quorum_ready_override=True, proof_done_override=True, proof_reconciled_override=True, controlled_ready_override=True)["v204_production_lock_controller_report.json"]
    assert ready["next_action_matrix_selection"] == "CONTROLLED_OPERATION_READY_PER_ORDER_ONLY_LOCKED"
    assert_staged_safe(d)


# --- safety / locks default across the whole bundle ---
def test_v195_to_v204_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v195_reports_for_tests,
        generate_all_v196_reports_for_tests,
        generate_all_v197_reports_for_tests,
        generate_all_v198_reports_for_tests,
        generate_all_v199_reports_for_tests,
        generate_all_v200_reports_for_tests,
        generate_all_v201_reports_for_tests,
        generate_all_v202_reports_for_tests,
        generate_all_v203_reports_for_tests,
        generate_all_v204_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
