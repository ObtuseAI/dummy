from __future__ import annotations

from predator_mesh import staged_gate_common as sgc
from scripts.generate_v185_reports import generate_all_v185_reports_for_tests
from scripts.generate_v186_reports import generate_all_v186_reports_for_tests
from scripts.generate_v187_reports import generate_all_v187_reports_for_tests
from scripts.generate_v188_reports import generate_all_v188_reports_for_tests
from scripts.generate_v189_reports import generate_all_v189_reports_for_tests
from scripts.generate_v190_reports import generate_all_v190_reports_for_tests
from scripts.generate_v191_reports import generate_all_v191_reports_for_tests
from scripts.generate_v192_reports import generate_all_v192_reports_for_tests
from scripts.generate_v193_reports import generate_all_v193_reports_for_tests
from scripts.generate_v194_reports import generate_all_v194_reports_for_tests
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


def dryrun_approval(phrase: str = sgc.LIMITED_AUTONOMY_DRYRUN_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "run limited autonomy dry-run evaluation only", "scope": sgc.LIMITED_AUTONOMY_DRYRUN_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def autonomy_approval(phrase: str = sgc.AUTONOMY_REVIEW_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "review limited autonomy eligibility only", "scope": sgc.AUTONOMY_REVIEW_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


def gate_approval(phrase: str = sgc.LIMITED_AUTONOMY_GATE_PHRASE) -> dict:
    return {"exact_phrase": phrase, "operator": "operator:chris", "timestamp": "2026-07-05T21:00:00Z", "reason": "prepare a limited autonomy gate only", "scope": sgc.LIMITED_AUTONOMY_GATE_SCOPE, "expiration": "2026-07-06T21:00:00Z"}


# --- V185 live-proof blocker closure ---
def test_v185_live_proof_blockers_audited() -> None:
    d = generate_all_v185_reports_for_tests()["v185_live_proof_blocker_controller_report.json"]
    assert d["live_proof_blocker_controller_status"] == "PASS_LIVE_PROOF_BLOCKERS_AUDITED"
    assert d["next_action_matrix_selection"] == "AWAIT_FIRST_REAL_PILOT_OR_CONTROLLED_SESSION_PROOF"
    assert d["live_orders"] == 0 and d["real_broker_contacted"] is False
    assert_staged_safe(d)


# --- V186 controlled session authority recheck ---
def test_v186_default_blocked_and_fixture_ready_no_submit() -> None:
    d = generate_all_v186_reports_for_tests()["v186_session_authority_controller_report.json"]
    assert d["session_authority_controller_status"] == "PARTIAL_CONTROLLED_SESSION_AUTHORITY_BLOCKED"
    ok = generate_all_v186_reports_for_tests(operation_approval=operation_approval(), session_approval=session_approval(), pilot_proof_override=True)["v186_session_authority_controller_report.json"]
    assert ok["session_authority_controller_status"] == "PASS_CONTROLLED_SESSION_AUTHORITY_READY_NO_SUBMIT"
    assert ok["live_orders"] == 0
    fuzzy = generate_all_v186_reports_for_tests(operation_approval=operation_approval("bad"), session_approval=session_approval(), pilot_proof_override=True)["v186_session_authority_controller_report.json"]
    assert fuzzy["session_authority_controller_status"] == "FAIL_CLOSED_INVALID_CONTROLLED_OPERATION_OR_SESSION_APPROVAL"
    assert_staged_safe(ok)


# --- V187 autonomy dry-run approval validator ---
def test_v187_default_absent_and_fixture_validated_no_live_path() -> None:
    d = generate_all_v187_reports_for_tests()["v187_autonomy_dryrun_controller_report.json"]
    assert d["autonomy_dryrun_controller_status"] == "PARTIAL_AUTONOMY_DRYRUN_APPROVAL_ABSENT"
    ok = generate_all_v187_reports_for_tests(dryrun_approval=dryrun_approval(), autonomy_approval=autonomy_approval())["v187_autonomy_dryrun_controller_report.json"]
    assert ok["autonomy_dryrun_controller_status"] == "PASS_AUTONOMY_DRYRUN_APPROVAL_VALIDATED_NO_LIVE_PATH"
    assert ok["real_broker_contacted"] is False and ok["live_orders"] == 0
    fuzzy = generate_all_v187_reports_for_tests(dryrun_approval=dryrun_approval("bad"))["v187_autonomy_dryrun_controller_report.json"]
    assert fuzzy["autonomy_dryrun_controller_status"] == "FAIL_CLOSED_INVALID_AUTONOMY_DRYRUN_APPROVAL"
    assert_staged_safe(ok)


# --- V188 autonomy shadow governor ---
def test_v188_shadow_governor_inert() -> None:
    d = generate_all_v188_reports_for_tests()["v188_shadow_governor_controller_report.json"]
    assert d["shadow_governor_controller_status"] == "PASS_AUTONOMY_SHADOW_GOVERNOR_LOCKED_INERT"
    assert d["autonomous_trading_enabled"] is False and d["live_orders"] == 0
    assert d["shadow_decision"] == "SHADOW_ABSTAIN"
    assert_staged_safe(d)


# --- V189 shadow decision forensic ---
def test_v189_shadow_forensic_reviewed() -> None:
    d = generate_all_v189_reports_for_tests()["v189_shadow_forensic_controller_report.json"]
    assert d["shadow_forensic_controller_status"] == "PASS_SHADOW_DECISION_FORENSIC_REVIEWED_LOCKED"
    assert d["live_orders"] == 0
    assert_staged_safe(d)


# --- V190 guarded autonomy eligibility quorum ---
def test_v190_default_blocked_and_fixture_ready_no_autonomy() -> None:
    d = generate_all_v190_reports_for_tests()["v190_autonomy_quorum_controller_report.json"]
    assert d["autonomy_quorum_controller_status"] == "PARTIAL_GUARDED_AUTONOMY_BLOCKED"
    assert d["autonomy_eligibility"] == "AUTONOMY_BLOCKED_NO_LIVE_PROOF"
    assert d["autonomous_trading_enabled"] is False
    ok = generate_all_v190_reports_for_tests(autonomy_approval=autonomy_approval(), dryrun_approval=dryrun_approval(), live_proof_override=True, shadow_ok_override=True)["v190_autonomy_quorum_controller_report.json"]
    assert ok["autonomy_quorum_controller_status"] == "PASS_GUARDED_AUTONOMY_REVIEW_READY_LOCKED"
    assert ok["autonomy_eligibility"] == "AUTONOMY_REVIEW_READY_LOCKED"
    assert ok["autonomous_trading_enabled"] is False
    fuzzy = generate_all_v190_reports_for_tests(autonomy_approval=autonomy_approval("bad"), dryrun_approval=dryrun_approval(), live_proof_override=True)["v190_autonomy_quorum_controller_report.json"]
    assert fuzzy["autonomy_quorum_controller_status"] == "FAIL_CLOSED_INVALID_AUTONOMY_APPROVAL"
    assert_staged_safe(ok)


# --- V191 limited autonomy gate ---
def test_v191_default_blocked_and_fixture_ready_no_live() -> None:
    d = generate_all_v191_reports_for_tests()["v191_limited_autonomy_gate_controller_report.json"]
    assert d["limited_autonomy_gate_controller_status"] == "PARTIAL_LIMITED_AUTONOMY_GATE_BLOCKED_NO_LIVE_PROOF"
    assert d["gate_state"] == "LIMITED_AUTONOMY_GATE_BLOCKED"
    assert d["live_orders"] == 0 and d["autonomous_trading_enabled"] is False
    ok = generate_all_v191_reports_for_tests(gate_approval=gate_approval(), quorum_ready_override=True)["v191_limited_autonomy_gate_controller_report.json"]
    assert ok["limited_autonomy_gate_controller_status"] == "PASS_LIMITED_AUTONOMY_GATE_READY_LOCKED"
    assert ok["gate_state"] == "LIMITED_AUTONOMY_GATE_READY_LOCKED"
    fuzzy = generate_all_v191_reports_for_tests(gate_approval=gate_approval("bad"), quorum_ready_override=True)["v191_limited_autonomy_gate_controller_report.json"]
    assert fuzzy["limited_autonomy_gate_controller_status"] == "FAIL_CLOSED_INVALID_LIMITED_AUTONOMY_GATE_APPROVAL"
    assert_staged_safe(ok)


# --- V192 guarded autonomy rehearsal session ---
def test_v192_rehearsal_dry_only() -> None:
    d = generate_all_v192_reports_for_tests()["v192_autonomy_rehearsal_controller_report.json"]
    assert d["autonomy_rehearsal_controller_status"] == "PASS_GUARDED_AUTONOMY_REHEARSAL_SESSION_READY_DRY_ONLY"
    assert d["autonomous_trading_enabled"] is False and d["live_orders"] == 0
    assert d["rehearsal_dry_only"] is True
    assert_staged_safe(d)


# --- V193 production hardening V6 ---
def test_v193_production_locks_hardened() -> None:
    d = generate_all_v193_reports_for_tests()["v193_production_hardening_controller_report.json"]
    assert d["production_hardening_controller_status"] == "PASS_PRODUCTION_LOCKS_HARDENED"
    assert d["caps_modified"] is False and d["autonomous_trading_enabled"] is False
    assert d["live_orders"] == 0
    assert_staged_safe(d)


# --- V194 production lock V6 ---
def test_v194_lock_summary_default_await_session_approval() -> None:
    d = generate_all_v194_reports_for_tests()["v194_production_lock_controller_report.json"]
    assert d["production_lock_controller_status"] == "PASS_PRODUCTION_LOCK_V6_SUMMARY_GENERATED"
    assert d["next_action_matrix_selection"] == "AWAIT_CONTROLLED_SESSION_APPROVAL"
    assert d["total_real_live_orders_submitted"] == 0
    assert d["autonomous_trading_enabled"] is False and d["scale_applied"] is False
    ready = generate_all_v194_reports_for_tests(session_authority_override=True, autonomy_ready_override=True)["v194_production_lock_controller_report.json"]
    assert ready["next_action_matrix_selection"] == "AWAIT_AUTONOMY_REVIEW_APPROVAL"
    assert_staged_safe(d)


# --- safety / locks default across the whole bundle ---
def test_v185_to_v194_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v185_reports_for_tests,
        generate_all_v186_reports_for_tests,
        generate_all_v187_reports_for_tests,
        generate_all_v188_reports_for_tests,
        generate_all_v189_reports_for_tests,
        generate_all_v190_reports_for_tests,
        generate_all_v191_reports_for_tests,
        generate_all_v192_reports_for_tests,
        generate_all_v193_reports_for_tests,
        generate_all_v194_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            assert_staged_safe(report)
