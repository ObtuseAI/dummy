from __future__ import annotations

from pathlib import Path

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v296.reports import armable_authority
from predator_mesh.v297.reports import ready_seal
from predator_mesh.v298.reports import full_authority_arm
from archive.report_scripts.generate_v295_reports import generate_all_v295_reports_for_tests
from archive.report_scripts.generate_v296_reports import generate_all_v296_reports_for_tests
from archive.report_scripts.generate_v297_reports import generate_all_v297_reports_for_tests
from archive.report_scripts.generate_v298_reports import generate_all_v298_reports_for_tests
from archive.report_scripts.generate_v299_reports import generate_all_v299_reports_for_tests
from archive.report_scripts.generate_v300_reports import generate_all_v300_reports_for_tests
from archive.report_scripts.generate_v301_reports import generate_all_v301_reports_for_tests
from archive.report_scripts.generate_v302_reports import generate_all_v302_reports_for_tests
from archive.report_scripts.generate_v303_reports import generate_all_v303_reports_for_tests
from archive.report_scripts.generate_v304_reports import generate_all_v304_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe

ROOT = Path(sgc.ROOT)

ATTEMPT = {"proof_id": "P1", "proof_target": "FIRST_REAL_PILOT_PROOF", "order_attempt_id": "A1", "idempotency_key": "K1", "timestamp": "2026-07-06T21:00:00Z", "attempt_status": "FILLED", "proof_lock": True, "adapter_response_shape": "accepted"}
PROOF = {"fill_state": "FILLED", "slippage_bucket": "low"}


def _safe(report: dict) -> None:
    assert_staged_safe(report)
    assert report.get("runtime_approvals_created_by_dummy") is False
    assert report.get("approval_files_written", 0) == 0
    assert report.get("real_live_orders_submitted_count", 0) == 0
    assert report.get("real_broker_contacted") is False
    assert report.get("scale_applied") is False
    assert report.get("autonomous_trading_enabled") is False
    assert report.get("market_order") is False


# --- V295 real-proof dependency cutoff baseline ---
def test_v295_real_proof_dependency_cutoff_baseline_ready() -> None:
    d = generate_all_v295_reports_for_tests()["v295_real_proof_dependency_cutoff_baseline_controller_report.json"]
    assert d["real_proof_dependency_cutoff_baseline_controller_status"] == "PASS_REAL_PROOF_DEPENDENCY_CUTOFF_BASELINE_READY"
    assert d["fork_classification"]["REAL_PROOF_DEPENDENCY_ACTIVE"] is True
    assert d["fork_classification"]["SCALE_AUTONOMY_BLOCKED_NO_REAL_PROOF"] is True
    assert d["canonical_next_action_list"]
    _safe(d)


# --- V296 operator execution fork: blocked default, armable fixture ---
def test_v296_operator_execution_fork_blocked_default() -> None:
    d = generate_all_v296_reports_for_tests()["v296_operator_execution_fork_controller_report.json"]
    assert d["operator_execution_fork_controller_status"] == "PARTIAL_OPERATOR_EXECUTION_FORK_LOCKED_AUTHORITY_ABSENT"
    assert d["fork_state"] == "FORK_LOCKED_AUTHORITY_ABSENT"
    assert d["order_submitted"] is False
    _safe(d)


def test_v296_operator_execution_fork_armable_fixture() -> None:
    d = generate_all_v296_reports_for_tests(authority=armable_authority())["v296_operator_execution_fork_controller_report.json"]
    assert d["operator_execution_fork_controller_status"] == "PASS_OPERATOR_EXECUTION_FORK_ARMABLE_NO_SUBMIT"
    assert d["fork_state"] == "FORK_ARMABLE_NO_SUBMIT"
    assert d["order_submitted"] is False
    _safe(d)


# --- V297 execute-once command seal: blocked default, fixture ready no submit ---
def test_v297_command_seal_blocked_default() -> None:
    d = generate_all_v297_reports_for_tests()["v297_execute_once_command_seal_controller_report.json"]
    assert d["execute_once_command_seal_controller_status"] == "PARTIAL_COMMAND_SEAL_BLOCKED_AUTHORITY_ABSENT"
    assert d["seal_state"] == "COMMAND_SEAL_BLOCKED_AUTHORITY_ABSENT"
    _safe(d)


def test_v297_command_seal_fixture_ready_no_submit() -> None:
    d = generate_all_v297_reports_for_tests(seal=ready_seal())["v297_execute_once_command_seal_controller_report.json"]
    assert d["execute_once_command_seal_controller_status"] == "PASS_EXECUTE_ONCE_COMMAND_SEAL_READY_NO_SUBMIT"
    assert d["seal_state"] == "COMMAND_SEAL_READY_NO_SUBMIT"
    assert sgc.CONTROLLED_PILOT_PHRASE not in str(d["seal_manifest"])
    _safe(d)


# --- V298 execute-once final proof runner: blocked default + fixture full-auth + block cases ---
def test_v298_final_proof_runner_not_armed_default() -> None:
    d = generate_all_v298_reports_for_tests()["v298_execute_once_final_proof_runner_v7_controller_report.json"]
    assert d["execute_once_final_proof_runner_v7_controller_status"] == "PARTIAL_EXECUTE_ONCE_FINAL_PROOF_RUNNER_NOT_ARMED"
    assert d["arm_state"] == "NOT_ARMED_DRY_DEFAULT"
    _safe(d)


def test_v298_final_proof_runner_fixture_full_auth_non_broker_double() -> None:
    d = generate_all_v298_reports_for_tests(arm=full_authority_arm())["v298_execute_once_final_proof_runner_v7_controller_report.json"]
    assert d["execute_once_final_proof_runner_v7_controller_status"] == "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED"
    assert d["uses_non_broker_double"] is True and d["submitted_autolocked"] is True
    assert d["real_live_orders"] == 0 and d["real_broker_contacted"] is False and d["market_order_submitted"] is False
    assert d["fixture_proof_inflates_real_score"] is False
    _safe(d)


def test_v298_final_proof_runner_block_cases() -> None:
    ctrl = "v298_execute_once_final_proof_runner_v7_controller_report.json"
    cases = {
        "env_mode": "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_ENV_GATE",
        "command_seal_ready": "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_NO_COMMAND_SEAL",
        "live_authorized": "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_NO_AUTHORITY",
        "approval_exact": "FAIL_CLOSED_EXECUTE_ONCE_FINAL_PROOF_RUNNER_APPROVAL_INVALID",
        "adapter_injected": "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_NO_ADAPTER",
        "limit_only": "FAIL_CLOSED_EXECUTE_ONCE_FINAL_PROOF_RUNNER_MARKET_ORDER_REJECTED",
        "not_repeat": "EXECUTE_ONCE_FINAL_PROOF_RUNNER_BLOCKED_REPEAT_AUTO_LOCKED",
    }
    for missing, expected in cases.items():
        arm = full_authority_arm(); arm[missing] = False
        d = generate_all_v298_reports_for_tests(arm=arm)[ctrl]
        assert d["execute_once_final_proof_runner_v7_controller_status"] == expected, missing
        assert d["real_live_orders_submitted_count"] == 0
        _safe(d)


# --- V299 post-proof auto intake: default no attempt, fixture ready ---
def test_v299_auto_intake_default_no_attempt() -> None:
    d = generate_all_v299_reports_for_tests()["v299_post_proof_auto_intake_v4_controller_report.json"]
    assert d["post_proof_auto_intake_v4_controller_status"] == "PARTIAL_NO_PROOF_ATTEMPT_TO_AUTO_INGEST"
    assert d["attempt_classification"] == "NO_ATTEMPT"
    _safe(d)


def test_v299_auto_intake_fixture_ready() -> None:
    d = generate_all_v299_reports_for_tests(attempt=ATTEMPT)["v299_post_proof_auto_intake_v4_controller_report.json"]
    assert d["post_proof_auto_intake_v4_controller_status"] == "PASS_POST_PROOF_AUTO_INTAKE_READY_FOR_RECONCILE"
    assert d["attempt_classification"] == "ATTEMPT_READY_FOR_RECONCILE"
    _safe(d)


# --- V300 reconcile/forensic orchestrator: default no proof, fixture pass ---
def test_v300_orchestrator_default_no_proof() -> None:
    d = generate_all_v300_reports_for_tests()["v300_reconcile_forensic_auto_orchestrator_v6_controller_report.json"]
    assert d["reconcile_forensic_auto_orchestrator_v6_controller_status"] == "PARTIAL_NO_PROOF_TO_RECONCILE_FORENSIC_ORCHESTRATE"
    assert d["fill_state"] == "NO_ATTEMPT"
    _safe(d)


def test_v300_orchestrator_fixture_reviewed_locked() -> None:
    d = generate_all_v300_reports_for_tests(proof=PROOF)["v300_reconcile_forensic_auto_orchestrator_v6_controller_report.json"]
    assert d["reconcile_forensic_auto_orchestrator_v6_controller_status"] == "PASS_RECONCILE_FORENSIC_AUTO_ORCHESTRATOR_V6_REVIEWED_LOCKED"
    assert d["fill_state"] == "FILLED" and d["private_data_redacted"] is True
    _safe(d)


# --- V301 post-proof route: blocked by no real proof, fixture pass ---
def test_v301_route_blocked_no_real_proof() -> None:
    d = generate_all_v301_reports_for_tests()["v301_post_proof_route_autopilot_controller_report.json"]
    assert d["post_proof_route_autopilot_controller_status"] == "PARTIAL_ROUTE_BLOCKED_NO_REAL_PROOF"
    assert d["route_state"] == "ROUTE_BLOCKED_NO_REAL_PROOF"
    _safe(d)


def test_v301_route_fixture_ready_locked() -> None:
    d = generate_all_v301_reports_for_tests(real_proof=True, reconcile=True, forensic=True)["v301_post_proof_route_autopilot_controller_report.json"]
    assert d["post_proof_route_autopilot_controller_status"] == "PASS_POST_PROOF_ROUTE_AUTOPILOT_READY_LOCKED"
    assert d["route_state"] == "ROUTE_REPEAT_PILOT_READY_LOCKED"
    _safe(d)


# --- V302 repeat/session bundle prep: blocked by no real proof, fixture pass ---
def test_v302_bundle_prep_blocked_no_real_proof() -> None:
    d = generate_all_v302_reports_for_tests()["v302_repeat_session_bundle_prep_controller_report.json"]
    assert d["repeat_session_bundle_prep_controller_status"] == "PARTIAL_BUNDLE_PREP_BLOCKED_NO_REAL_PROOF"
    assert d["bundle_prep_state"] == "BUNDLE_PREP_BLOCKED_NO_REAL_PROOF"
    _safe(d)


def test_v302_bundle_prep_fixture_ready_locked() -> None:
    d = generate_all_v302_reports_for_tests(real_proof=True, reconcile=True, forensic=True)["v302_repeat_session_bundle_prep_controller_report.json"]
    assert d["repeat_session_bundle_prep_controller_status"] == "PASS_REPEAT_SESSION_BUNDLE_PREP_READY_LOCKED"
    assert d["bundle_prep_state"] == "BUNDLE_PREP_REPEAT_READY_LOCKED"
    _safe(d)


# --- V303 proof-starvation stop rule active with no real proof ---
def test_v303_proof_starvation_stop_rule_active() -> None:
    d = generate_all_v303_reports_for_tests()["v303_proof_starvation_stop_rule_controller_report.json"]
    assert d["proof_starvation_stop_rule_controller_status"] == "PASS_PROOF_STARVATION_STOP_RULE_ACTIVE"
    assert d["architecture_sprawl_blocked"] is True
    assert d["real_proof_present"] is False
    assert d["starvation_state"] in ("PROOF_STARVATION_ACTIVE", "OPERATOR_AUTHORITY_REQUIRED_STOP_ARCHITECTURE_SPRAWL")
    # Real proof present would flip to continue and unblock sprawl.
    rp = generate_all_v303_reports_for_tests(real_proof_override=True)["v303_proof_starvation_stop_rule_controller_report.json"]
    assert rp["starvation_state"] == "REAL_PROOF_PRESENT_CONTINUE"
    assert rp["architecture_sprawl_blocked"] is False
    _safe(d)


# --- V304 completion lift V10: fixtures never inflate real proof ---
def test_v304_completion_lift_no_fixture_inflation() -> None:
    d = generate_all_v304_reports_for_tests()["v304_completion_lift_v10_controller_report.json"]
    assert d["completion_lift_v10_controller_status"] == "PASS_COMPLETION_LIFT_V10_REAL_PROOF_FORK_LOCKED"
    assert d["subsystem_percentages"]["first_live_proof"] == 0
    assert d["real_first_live_proof_present"] is False
    assert d["fixture_proof_inflates_real_score"] is False
    assert d["scale_autonomy_blocked_by_no_live_proof"] is True
    assert d["proof_starvation_stop_rule_active"] is True
    assert d["subsystem_percentages"]["scale_review"] == 0 and d["subsystem_percentages"]["autonomy_review"] == 0
    assert d["real_proof_fork_locked"] is True
    _safe(d)


# --- safety / locks default across the whole bundle ---
def test_v295_to_v304_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v295_reports_for_tests, generate_all_v296_reports_for_tests, generate_all_v297_reports_for_tests,
        generate_all_v298_reports_for_tests, generate_all_v299_reports_for_tests, generate_all_v300_reports_for_tests,
        generate_all_v301_reports_for_tests, generate_all_v302_reports_for_tests, generate_all_v303_reports_for_tests,
        generate_all_v304_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            _safe(report)


# --- Dummy never creates runtime/approvals during generation ---
def test_dummy_does_not_create_runtime_approvals() -> None:
    existed_before = (ROOT / "runtime" / "approvals").exists()
    for gen in (generate_all_v296_reports_for_tests, generate_all_v298_reports_for_tests, generate_all_v304_reports_for_tests):
        gen()
    assert (ROOT / "runtime" / "approvals").exists() == existed_before
