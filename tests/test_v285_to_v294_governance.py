from __future__ import annotations

from pathlib import Path

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v289.reports import full_authority_arm
from archive.report_scripts.generate_v285_reports import generate_all_v285_reports_for_tests
from archive.report_scripts.generate_v286_reports import generate_all_v286_reports_for_tests
from archive.report_scripts.generate_v287_reports import generate_all_v287_reports_for_tests
from archive.report_scripts.generate_v288_reports import generate_all_v288_reports_for_tests
from archive.report_scripts.generate_v289_reports import generate_all_v289_reports_for_tests
from archive.report_scripts.generate_v290_reports import generate_all_v290_reports_for_tests
from archive.report_scripts.generate_v291_reports import generate_all_v291_reports_for_tests
from archive.report_scripts.generate_v292_reports import generate_all_v292_reports_for_tests
from archive.report_scripts.generate_v293_reports import generate_all_v293_reports_for_tests
from archive.report_scripts.generate_v294_reports import generate_all_v294_reports_for_tests
from tests.staged_gate_test_helpers import assert_staged_safe

ROOT = Path(sgc.ROOT)


def valid_manifest() -> dict:
    return {
        "version": "v3", "proof_target": "FIRST_REAL_PILOT_PROOF",
        "approvals": {"exact_phrase": sgc.CONTROLLED_PILOT_PHRASE, "acknowledgments": "no market order; strict caps"},
        "config_descriptors": {"live_submit": True, "caps": True}, "adapter_descriptors": {"firewall": True},
        "operator_metadata": {"operator": "operator:chris", "timestamp": "2026-07-06T21:00:00Z"},
        "expiry": "2026-07-07T21:00:00Z", "scope": sgc.CONTROLLED_PILOT_SCOPE, "reason": "controlled pilot",
    }


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


# --- V285 first-proof final run baseline ---
def test_v285_first_proof_final_run_baseline_ready() -> None:
    d = generate_all_v285_reports_for_tests()["v285_first_proof_final_run_baseline_controller_report.json"]
    assert d["first_proof_final_run_baseline_controller_status"] == "PASS_FIRST_PROOF_FINAL_RUN_BASELINE_READY"
    assert d["appliance_state_classification"]["FINAL_RUN_APPLIANCE_READY_FOR_BUILD"] is True
    assert d["canonical_next_action_list"]
    _safe(d)


# --- V286 external authority seal verifier: absent / fixture / fuzzy / broad ---
def test_v286_authority_seal_absent_fixture_fuzzy_broad() -> None:
    ctrl = "v286_external_authority_seal_verifier_controller_report.json"
    d = generate_all_v286_reports_for_tests()[ctrl]
    assert d["external_authority_seal_verifier_controller_status"] == "PARTIAL_AUTHORITY_SEAL_BLOCKED_MANIFEST_ABSENT"
    assert d["seal_state"] == "SEAL_BLOCKED_MANIFEST_ABSENT"
    ok = generate_all_v286_reports_for_tests(manifest=valid_manifest())[ctrl]
    assert ok["external_authority_seal_verifier_controller_status"] == "PASS_AUTHORITY_SEAL_VERIFIED_READY_FOR_ARMABILITY"
    assert ok["seal_state"] == "SEAL_READY_FOR_ARMABILITY"
    assert sgc.CONTROLLED_PILOT_PHRASE not in str(ok.get("approval_hash", ""))
    assert ok["raw_phrase_serialized"] is False
    fuzzy_m = valid_manifest(); fuzzy_m["approvals"] = {"exact_phrase": "bad"}
    fuzzy = generate_all_v286_reports_for_tests(manifest=fuzzy_m)[ctrl]
    assert fuzzy["external_authority_seal_verifier_controller_status"] == "FAIL_CLOSED_AUTHORITY_SEAL_APPROVAL_PHRASE_INVALID"
    broad_m = valid_manifest(); broad_m["reason"] = "grant full live trading approval to trade live markets"
    broad = generate_all_v286_reports_for_tests(manifest=broad_m)[ctrl]
    assert broad["external_authority_seal_verifier_controller_status"] == "FAIL_CLOSED_AUTHORITY_SEAL_BROAD_APPROVAL_REJECTED"
    assert broad["broad_language_rejected"] is True
    _safe(ok)


# --- V287 final run appliance dry default ---
def test_v287_final_run_appliance_dry_default() -> None:
    d = generate_all_v287_reports_for_tests()["v287_final_run_appliance_launcher_controller_report.json"]
    assert d["final_run_appliance_launcher_controller_status"] == "PASS_FINAL_RUN_APPLIANCE_DRY_COMPLETE"
    assert d["dry_pipeline_step_count"] == 8
    assert d["livebrokerfirewall_submit_called"] is False
    assert d["config_caps_mutated"] is False
    _safe(d)


# --- V288 no-surprises precheck: blocked default, fixture pass ---
def test_v288_no_surprises_precheck_blocked_default() -> None:
    d = generate_all_v288_reports_for_tests()["v288_live_proof_no_surprises_precheck_controller_report.json"]
    assert d["live_proof_no_surprises_precheck_controller_status"] == "PARTIAL_NO_SURPRISES_PRECHECK_BLOCKED_AUTHORITY"
    assert d["precheck_state"] == "PRECHECK_BLOCKED_AUTHORITY"
    _safe(d)


def test_v288_no_surprises_precheck_fixture_ready() -> None:
    d = generate_all_v288_reports_for_tests(seal=True, config_caps=True, adapter=True, env_gate=True, freeze=True)["v288_live_proof_no_surprises_precheck_controller_report.json"]
    assert d["live_proof_no_surprises_precheck_controller_status"] == "PASS_NO_SURPRISES_PRECHECK_READY_NO_SUBMIT"
    assert d["all_green"] is True
    _safe(d)


# --- V289 execute-once final run: blocked default + fixture full-auth non-broker double + block cases ---
def test_v289_execute_once_final_run_not_armed_default() -> None:
    d = generate_all_v289_reports_for_tests()["v289_execute_once_final_run_wrapper_v6_controller_report.json"]
    assert d["execute_once_final_run_wrapper_v6_controller_status"] == "PARTIAL_EXECUTE_ONCE_FINAL_RUN_NOT_ARMED"
    assert d["arm_state"] == "NOT_ARMED_DRY_DEFAULT"
    _safe(d)


def test_v289_execute_once_final_run_fixture_full_auth_non_broker_double() -> None:
    d = generate_all_v289_reports_for_tests(arm=full_authority_arm())["v289_execute_once_final_run_wrapper_v6_controller_report.json"]
    assert d["execute_once_final_run_wrapper_v6_controller_status"] == "PASS_EXECUTE_ONCE_FINAL_RUN_SUBMITTED_AUTOLOCKED"
    assert d["uses_non_broker_double"] is True and d["submitted_autolocked"] is True
    assert d["real_live_orders"] == 0 and d["real_broker_contacted"] is False and d["market_order_submitted"] is False
    assert d["fixture_proof_inflates_real_score"] is False
    _safe(d)


def test_v289_execute_once_final_run_block_cases() -> None:
    ctrl = "v289_execute_once_final_run_wrapper_v6_controller_report.json"
    cases = {
        "env_mode": "EXECUTE_ONCE_FINAL_RUN_BLOCKED_ENV_GATE",
        "precheck_ready": "EXECUTE_ONCE_FINAL_RUN_BLOCKED_NO_PRECHECK",
        "live_authorized": "EXECUTE_ONCE_FINAL_RUN_BLOCKED_NO_AUTHORITY",
        "approval_exact": "FAIL_CLOSED_EXECUTE_ONCE_FINAL_RUN_APPROVAL_INVALID",
        "adapter_injected": "EXECUTE_ONCE_FINAL_RUN_BLOCKED_NO_ADAPTER",
        "limit_only": "FAIL_CLOSED_EXECUTE_ONCE_FINAL_RUN_MARKET_ORDER_REJECTED",
        "not_repeat": "EXECUTE_ONCE_FINAL_RUN_BLOCKED_REPEAT_AUTO_LOCKED",
    }
    for missing, expected in cases.items():
        arm = full_authority_arm(); arm[missing] = False
        d = generate_all_v289_reports_for_tests(arm=arm)[ctrl]
        assert d["execute_once_final_run_wrapper_v6_controller_status"] == expected, missing
        assert d["real_live_orders_submitted_count"] == 0
        _safe(d)


# --- V290 post-proof autopilot intake: default no attempt, fixture ready ---
def test_v290_autopilot_intake_default_no_attempt() -> None:
    d = generate_all_v290_reports_for_tests()["v290_post_proof_autopilot_intake_controller_report.json"]
    assert d["post_proof_autopilot_intake_controller_status"] == "PARTIAL_NO_PROOF_ATTEMPT_TO_AUTOPILOT_INGEST"
    assert d["attempt_classification"] == "NO_ATTEMPT"
    _safe(d)


def test_v290_autopilot_intake_fixture_ready() -> None:
    d = generate_all_v290_reports_for_tests(attempt=ATTEMPT)["v290_post_proof_autopilot_intake_controller_report.json"]
    assert d["post_proof_autopilot_intake_controller_status"] == "PASS_POST_PROOF_AUTOPILOT_INTAKE_READY_FOR_RECONCILE"
    assert d["attempt_classification"] == "ATTEMPT_READY_FOR_RECONCILE"
    _safe(d)


# --- V291 reconcile/forensic autopipeline: default no proof, fixture pass ---
def test_v291_autopipeline_default_no_proof() -> None:
    d = generate_all_v291_reports_for_tests()["v291_reconcile_forensic_autopipeline_v5_controller_report.json"]
    assert d["reconcile_forensic_autopipeline_v5_controller_status"] == "PARTIAL_NO_PROOF_TO_RECONCILE_FORENSIC_AUTOPIPELINE"
    assert d["fill_state"] == "NO_ATTEMPT"
    _safe(d)


def test_v291_autopipeline_fixture_reviewed_locked() -> None:
    d = generate_all_v291_reports_for_tests(proof=PROOF)["v291_reconcile_forensic_autopipeline_v5_controller_report.json"]
    assert d["reconcile_forensic_autopipeline_v5_controller_status"] == "PASS_RECONCILE_FORENSIC_AUTOPIPELINE_V5_REVIEWED_LOCKED"
    assert d["fill_state"] == "FILLED" and d["private_data_redacted"] is True
    _safe(d)


# --- V292 repeat/session fast route: blocked by no live proof, fixture pass ---
def test_v292_fast_route_blocked_no_live_proof() -> None:
    d = generate_all_v292_reports_for_tests()["v292_repeat_session_fast_route_prep_controller_report.json"]
    assert d["repeat_session_fast_route_prep_controller_status"] == "PARTIAL_FAST_ROUTE_BLOCKED_NO_LIVE_PROOF"
    assert d["fast_route_state"] == "FAST_ROUTE_BLOCKED_NO_LIVE_PROOF"
    _safe(d)


def test_v292_fast_route_fixture_ready_locked() -> None:
    d = generate_all_v292_reports_for_tests(first_live_proof=True, reconcile=True, forensic=True)["v292_repeat_session_fast_route_prep_controller_report.json"]
    assert d["repeat_session_fast_route_prep_controller_status"] == "PASS_REPEAT_SESSION_FAST_ROUTE_READY_LOCKED"
    assert d["fast_route_state"] == "FAST_ROUTE_REPEAT_READY_LOCKED"
    _safe(d)


# --- V293 real-proof-required wall blocks fixture proof ---
def test_v293_wall_locks_and_fixture_proof_does_not_unlock() -> None:
    d = generate_all_v293_reports_for_tests()["v293_real_proof_required_scale_autonomy_wall_controller_report.json"]
    assert d["real_proof_required_scale_autonomy_wall_controller_status"] == "PASS_REAL_PROOF_REQUIRED_WALL_LOCKED"
    assert d["proof_classification"] == "NO_PROOF"
    assert d["scale_state"] == "SCALE_BLOCKED_NO_REAL_PROOF" and d["autonomy_state"] == "AUTONOMY_BLOCKED_NO_REAL_PROOF"
    # Fixture proof only must NOT unlock scale/autonomy.
    fx = generate_all_v293_reports_for_tests(fixture_proof=True)["v293_real_proof_required_scale_autonomy_wall_controller_report.json"]
    assert fx["proof_classification"] == "FIXTURE_PROOF_ONLY"
    assert fx["scale_unlocked"] is False and fx["autonomy_unlocked"] is False
    assert fx["fixture_proof_unlocks_scale_autonomy"] is False
    _safe(d)
    _safe(fx)


# --- V294 completion lift V9: fixtures never inflate real proof ---
def test_v294_completion_lift_no_fixture_inflation() -> None:
    d = generate_all_v294_reports_for_tests()["v294_completion_lift_v9_controller_report.json"]
    assert d["completion_lift_v9_controller_status"] == "PASS_COMPLETION_LIFT_V9_FINAL_PROOF_READY_LOCKED"
    assert d["subsystem_percentages"]["first_live_proof"] == 0
    assert d["real_first_live_proof_present"] is False
    assert d["fixture_proof_inflates_real_score"] is False
    assert d["scale_autonomy_blocked_by_no_live_proof"] is True
    assert d["subsystem_percentages"]["scale_review"] == 0 and d["subsystem_percentages"]["autonomy_review"] == 0
    assert d["route_locked"] is True
    _safe(d)


# --- safety / locks default across the whole bundle ---
def test_v285_to_v294_safety_and_locks_default() -> None:
    for gen in (
        generate_all_v285_reports_for_tests, generate_all_v286_reports_for_tests, generate_all_v287_reports_for_tests,
        generate_all_v288_reports_for_tests, generate_all_v289_reports_for_tests, generate_all_v290_reports_for_tests,
        generate_all_v291_reports_for_tests, generate_all_v292_reports_for_tests, generate_all_v293_reports_for_tests,
        generate_all_v294_reports_for_tests,
    ):
        for name, report in gen().items():
            if name.startswith("final_report_"):
                continue
            _safe(report)


# --- Dummy never creates runtime/approvals during generation ---
def test_dummy_does_not_create_runtime_approvals() -> None:
    existed_before = (ROOT / "runtime" / "approvals").exists()
    for gen in (generate_all_v286_reports_for_tests, generate_all_v289_reports_for_tests, generate_all_v294_reports_for_tests):
        gen()
    assert (ROOT / "runtime" / "approvals").exists() == existed_before
