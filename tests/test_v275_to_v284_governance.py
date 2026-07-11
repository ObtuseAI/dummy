from __future__ import annotations

from pathlib import Path

from predator_mesh import staged_gate_common as sgc
from archive.report_scripts.generate_v275_reports import generate_all_v275_reports_for_tests
from archive.report_scripts.generate_v276_reports import generate_all_v276_reports_for_tests
from archive.report_scripts.generate_v277_reports import generate_all_v277_reports_for_tests
from archive.report_scripts.generate_v278_reports import generate_all_v278_reports_for_tests
from archive.report_scripts.generate_v279_reports import generate_all_v279_reports_for_tests
from archive.report_scripts.generate_v280_reports import generate_all_v280_reports_for_tests
from archive.report_scripts.generate_v281_reports import generate_all_v281_reports_for_tests
from archive.report_scripts.generate_v282_reports import generate_all_v282_reports_for_tests
from archive.report_scripts.generate_v283_reports import generate_all_v283_reports_for_tests
from archive.report_scripts.generate_v284_reports import generate_all_v284_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe

ROOT = Path(sgc.ROOT)

ATTEMPT = {"proof_id": "P1", "proof_target": "FIRST_REAL_PILOT_PROOF", "attempt_id": "A1", "idempotency_key": "K1", "proof_lock": True, "timestamp": "2026-07-06T21:00:00Z", "state": "ATTEMPT_DETECTED", "adapter_response_shape": "accepted"}
PROOF = {"proof_id": "P1", "reconcile": True, "forensic": True}


def _safe(report: dict) -> None:
    assert_staged_safe(report)
    assert report.get("runtime_approvals_created_by_dummy") is False
    assert report.get("approval_files_written", 0) == 0
    assert report.get("real_live_orders_submitted_count", 0) == 0
    assert report.get("real_broker_contacted") is False
    assert report.get("scale_applied") is False
    assert report.get("autonomous_trading_enabled") is False
    assert report.get("market_order") is False


# --- V275 final operator execution baseline ---
def test_v275_final_operator_execution_baseline_ready() -> None:
    d = generate_all_v275_reports_for_tests()["v275_final_operator_execution_baseline_controller_report.json"]
    assert d["final_operator_execution_baseline_controller_status"] == "PASS_FINAL_OPERATOR_EXECUTION_BASELINE_READY"
    assert d["appliance_state_classification"]["EXECUTION_CONSOLE_READY_FOR_BUILD"] is True
    assert d["canonical_next_action_list"]
    assert d["execution_console_ready_for_build"] is True
    _safe(d)


# --- V276 final authority readiness console read-only ---
def test_v276_console_read_only_flags() -> None:
    d = generate_all_v276_reports_for_tests()["v276_final_authority_readiness_console_controller_report.json"]
    assert d["final_authority_readiness_console_controller_status"] == "PASS_FINAL_AUTHORITY_READINESS_CONSOLE_READY_READONLY"
    for flag in ("ui_submit_enabled", "ui_writes_enabled", "ui_runtime_approvals_create_enabled", "ui_caps_edit_enabled", "ui_live_submit_edit_enabled"):
        assert d[flag] is False
    assert d["console_can_submit"] is False
    assert d["authority_readiness_matrix"]
    _safe(d)


# --- V277 final live-proof runbook lock command sequence ---
def test_v277_runbook_lock_command_sequence() -> None:
    d = generate_all_v277_reports_for_tests()["v277_final_live_proof_runbook_lock_controller_report.json"]
    assert d["final_live_proof_runbook_lock_controller_status"] == "PASS_FINAL_LIVE_PROOF_RUNBOOK_LOCK_READY"
    assert d["command_count"] == 10 and len(d["command_sequence"]) == 10
    assert d["env_gate"]["DUMMY_LIVE_PROOF_MODE"] == "1"
    assert d["env_gate"]["DUMMY_LIVE_PROOF_ACK"] == "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
    assert d["max_attempts"] == 1 and d["auto_lock_after_attempt"] is True
    assert d["fail_closed_expectations"] and d["success_expectations"]
    _safe(d)


# --- V278 execute-once authority rehearsal V2 fixture-only ---
def test_v278_authority_rehearsal_fixture_only_no_real_order() -> None:
    d = generate_all_v278_reports_for_tests()["v278_execute_once_authority_rehearsal_v2_controller_report.json"]
    assert d["execute_once_authority_rehearsal_v2_controller_status"] == "PASS_EXECUTE_ONCE_AUTHORITY_REHEARSAL_V2_COMPLETE_FIXTURE_ONLY"
    assert d["rehearsal_case_count"] == 10
    fx = d["full_authority_fixture"]
    assert fx["uses_non_broker_double"] is True and fx["submitted_autolocked"] is True
    assert fx["real_live_orders"] == 0 and fx["real_broker_contacted"] is False and fx["market_order"] is False
    assert d["fixture_proof_inflates_real_score"] is False
    _safe(d)


# --- V279 live-proof attempt monitor: default no attempt, fixture ready ---
def test_v279_attempt_monitor_default_no_attempt() -> None:
    d = generate_all_v279_reports_for_tests()["v279_live_proof_attempt_monitor_controller_report.json"]
    assert d["live_proof_attempt_monitor_controller_status"] == "PARTIAL_NO_LIVE_PROOF_ATTEMPT_TO_MONITOR"
    assert d["attempt_classification"] == "NO_ATTEMPT"
    assert d["no_new_order_proof_status"] == "PASS_NO_NEW_ORDER"
    _safe(d)


def test_v279_attempt_monitor_fixture_ready_for_intake() -> None:
    d = generate_all_v279_reports_for_tests(attempt=ATTEMPT)["v279_live_proof_attempt_monitor_controller_report.json"]
    assert d["live_proof_attempt_monitor_controller_status"] == "PASS_LIVE_PROOF_ATTEMPT_MONITOR_READY_FOR_INTAKE"
    assert d["attempt_classification"] == "ATTEMPT_DETECTED_READY_FOR_INTAKE"
    assert d["monitored_attempt"]["proof_id"] == "P1"
    _safe(d)


# --- V280 post-proof reconcile/forensic launcher: default no proof, fixture pass ---
def test_v280_launcher_default_no_proof() -> None:
    d = generate_all_v280_reports_for_tests()["v280_post_proof_reconcile_forensic_launcher_controller_report.json"]
    assert d["post_proof_reconcile_forensic_launcher_controller_status"] == "PARTIAL_NO_PROOF_TO_RECONCILE_FORENSIC"
    assert d["proof_state"] == "NO_PROOF"
    _safe(d)


def test_v280_launcher_fixture_reviewed_locked() -> None:
    d = generate_all_v280_reports_for_tests(proof=PROOF)["v280_post_proof_reconcile_forensic_launcher_controller_report.json"]
    assert d["post_proof_reconcile_forensic_launcher_controller_status"] == "PASS_POST_PROOF_RECONCILE_FORENSIC_LAUNCHER_REVIEWED_LOCKED"
    assert d["completion_scoreboard_updated"] is True
    _safe(d)


# --- V281 repeat readiness blocked by no live proof, fixture pass ---
def test_v281_repeat_readiness_blocked_no_live_proof() -> None:
    d = generate_all_v281_reports_for_tests()["v281_repeat_pilot_post_proof_readiness_controller_report.json"]
    assert d["repeat_pilot_post_proof_readiness_controller_status"] == "PARTIAL_REPEAT_POST_PROOF_READINESS_BLOCKED_NO_LIVE_PROOF"
    assert d["repeat_state"] == "REPEAT_BLOCKED_NO_LIVE_PROOF"
    _safe(d)


def test_v281_repeat_readiness_fixture_ready_locked() -> None:
    d = generate_all_v281_reports_for_tests(first_live_proof=True, reconcile=True, forensic=True)["v281_repeat_pilot_post_proof_readiness_controller_report.json"]
    assert d["repeat_pilot_post_proof_readiness_controller_status"] == "PASS_REPEAT_POST_PROOF_READINESS_READY_LOCKED"
    assert d["repeat_state"] == "REPEAT_REVIEW_READY_LOCKED"
    _safe(d)


# --- V282 controlled session readiness blocked by no live proof, fixture pass ---
def test_v282_session_readiness_blocked_no_live_proof() -> None:
    d = generate_all_v282_reports_for_tests()["v282_controlled_session_post_proof_readiness_controller_report.json"]
    assert d["controlled_session_post_proof_readiness_controller_status"] == "PARTIAL_CONTROLLED_SESSION_POST_PROOF_READINESS_BLOCKED_NO_LIVE_PROOF"
    assert d["session_state"] == "SESSION_BLOCKED_NO_LIVE_PROOF"
    _safe(d)


def test_v282_session_readiness_fixture_ready_locked() -> None:
    d = generate_all_v282_reports_for_tests(first_live_proof=True, reconcile=True, forensic=True)["v282_controlled_session_post_proof_readiness_controller_report.json"]
    assert d["controlled_session_post_proof_readiness_controller_status"] == "PASS_CONTROLLED_SESSION_POST_PROOF_READINESS_READY_LOCKED"
    assert d["session_state"] == "SESSION_REVIEW_READY_LOCKED"
    _safe(d)


# --- V283 route command center read-only ---
def test_v283_route_command_center_read_only() -> None:
    d = generate_all_v283_reports_for_tests()["v283_route_command_center_v2_controller_report.json"]
    assert d["route_command_center_v2_controller_status"] == "PASS_ROUTE_COMMAND_CENTER_V2_READY_READONLY"
    assert d["route_state"] == "ROUTE_BLOCKED_NO_LIVE_PROOF"
    for flag in ("ui_submit_enabled", "ui_scale_enabled", "ui_autonomy_enabled", "ui_writes_enabled"):
        assert d[flag] is False
    _safe(d)


# --- V284 completion lift V8: fixtures never inflate real proof ---
def test_v284_completion_lift_no_fixture_inflation() -> None:
    d = generate_all_v284_reports_for_tests()["v284_completion_lift_v8_controller_report.json"]
    assert d["completion_lift_v8_controller_status"] == "PASS_COMPLETION_LIFT_V8_FINAL_OPERATOR_LOCKED"
    assert d["subsystem_percentages"]["first_live_proof"] == 0
    assert d["real_first_live_proof_present"] is False
    assert d["fixture_proof_inflates_real_score"] is False
    assert d["scale_autonomy_blocked_by_no_live_proof"] is True
    assert d["subsystem_percentages"]["scale_review"] == 0 and d["subsystem_percentages"]["autonomy_review"] == 0
    assert d["route_locked"] is True
    _safe(d)


# --- safety / locks default across the whole bundle ---
def test_v275_to_v284_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v275_reports_for_tests, generate_all_v276_reports_for_tests, generate_all_v277_reports_for_tests,
        generate_all_v278_reports_for_tests, generate_all_v279_reports_for_tests, generate_all_v280_reports_for_tests,
        generate_all_v281_reports_for_tests, generate_all_v282_reports_for_tests, generate_all_v283_reports_for_tests,
        generate_all_v284_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            _safe(report)


# --- Dummy never creates runtime/approvals during generation ---
def test_dummy_does_not_create_runtime_approvals() -> None:
    existed_before = (ROOT / "runtime" / "approvals").exists()
    for gen in (generate_all_v279_reports_for_tests, generate_all_v281_reports_for_tests, generate_all_v284_reports_for_tests):
        gen()
    assert (ROOT / "runtime" / "approvals").exists() == existed_before
