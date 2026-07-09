from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v31.reports import V31ReportFactory

router = APIRouter(prefix="/api/v31", tags=["v31"])


def _reports() -> dict[str, dict[str, Any]]:
    return V31ReportFactory(enable_network=False, env={}).build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice("dummy_mission_state_report_v17.json")


@router.get("/gate")
async def gate() -> dict[str, Any]:
    return _slice(
        "explicit_public_probe_operator_gate_v3_report.json",
        "public_probe_gate_intent_v1_report.json",
        "public_probe_environment_flag_v1_report.json",
        "public_probe_operator_acknowledgement_v1_report.json",
        "public_probe_gate_decision_v1_report.json",
        "public_probe_gate_safety_proof_v1_report.json",
        "public_probe_gate_config_diff_proof_v1_report.json",
    )


@router.get("/probe-runner")
async def probe_runner() -> dict[str, Any]:
    return _slice(
        "v30_adapter_public_probe_runner_v1_report.json",
        "adapter_probe_run_plan_v1_report.json",
        "adapter_probe_task_v1_report.json",
        "adapter_probe_result_v1_report.json",
        "adapter_probe_failure_v1_report.json",
        "adapter_probe_budget_v1_report.json",
        "adapter_probe_redaction_proof_v1_report.json",
    )


@router.get("/evidence")
async def evidence() -> dict[str, Any]:
    return _slice(
        "live_public_evidence_capture_v1_report.json",
        "live_public_evidence_packet_v1_report.json",
        "live_public_evidence_source_ref_v1_report.json",
        "live_public_evidence_freshness_v1_report.json",
        "live_public_evidence_eligibility_v1_report.json",
        "live_public_evidence_blocker_v1_report.json",
        "probe_evidence_normalization_pipeline_v2_report.json",
        "normalized_probe_evidence_v1_report.json",
    )


@router.get("/probes")
async def probes() -> dict[str, Any]:
    return _slice(
        "weather_public_probe_implementation_v2_report.json",
        "crypto_public_probe_implementation_v2_report.json",
        "public_event_reference_probe_implementation_v2_report.json",
        "kalshi_readonly_rule_probe_implementation_v2_report.json",
    )


@router.get("/closure")
async def closure() -> dict[str, Any]:
    return _slice(
        "due_forecast_live_observation_closure_v4_report.json",
        "due_forecast_live_observation_candidate_v1_report.json",
        "due_forecast_live_evidence_join_v1_report.json",
        "due_forecast_live_observation_decision_v1_report.json",
        "due_forecast_live_observation_ledger_write_v1_report.json",
        "due_forecast_live_observation_blocker_v1_report.json",
    )


@router.get("/scoring")
async def scoring() -> dict[str, Any]:
    return _slice(
        "live_score_seed_v2_report.json",
        "live_score_seed_candidate_v2_report.json",
        "live_score_seed_decision_v2_report.json",
        "live_score_metric_v2_report.json",
        "live_score_ledger_write_v2_report.json",
        "live_score_seed_blocker_v2_report.json",
        "live_calibration_seed_v2_report.json",
        "live_calibration_seed_sample_v2_report.json",
        "live_calibration_low_sample_warning_v2_report.json",
    )


@router.get("/cache-audit")
async def cache_audit() -> dict[str, Any]:
    return _slice(
        "public_probe_cache_writer_v1_report.json",
        "public_probe_cache_record_v1_report.json",
        "public_probe_cache_manifest_v1_report.json",
        "public_probe_cache_redaction_v1_report.json",
        "probe_run_audit_ledger_v1_report.json",
        "probe_run_source_summary_v1_report.json",
        "probe_run_outcome_summary_v1_report.json",
        "probe_run_safety_summary_v1_report.json",
    )


@router.get("/source-truth")
async def source_truth() -> dict[str, Any]:
    return _slice(
        "sports_fixture_guard_recheck_v2_report.json",
        "probe_source_truth_v12_report.json",
        "probe_health_truth_signal_v1_report.json",
        "public_evidence_truth_signal_v1_report.json",
        "observation_closure_truth_signal_v1_report.json",
        "live_score_truth_signal_v3_report.json",
        "public_probe_partial_reduction_v1_report.json",
        "public_probe_sprint_queue_v8_report.json",
        "probe_to_score_compounding_control_plane_v15_report.json",
        "domain_market_class_scoreboard_v16_report.json",
    )


@router.get("/safety")
async def safety() -> dict[str, Any]:
    return _slice(
        "no_secret_leak_report_v31.json",
        "no_source_api_key_leak_report_v31.json",
        "no_github_token_leak_report_v31.json",
        "no_direct_order_bypass_report_v31.json",
        "no_direct_cancel_bypass_report_v31.json",
        "no_browser_automation_report_v31.json",
        "no_pageagent_report_v31.json",
        "no_dom_extraction_report_v31.json",
        "no_mined_repo_clone_report_v31.json",
        "no_mined_repo_import_report_v31.json",
        "no_mined_repo_execution_report_v31.json",
        "no_public_probe_gate_to_execution_bridge_report_v31.json",
        "no_public_probe_runner_to_execution_bridge_report_v31.json",
        "no_live_public_evidence_to_execution_bridge_report_v31.json",
        "no_probe_normalization_to_execution_bridge_report_v31.json",
        "no_due_observation_closure_to_execution_bridge_report_v31.json",
        "no_live_score_seed_to_execution_bridge_report_v31.json",
        "no_public_probe_failure_scored_live_report_v31.json",
        "blunder_separation_recheck_v31.json",
        "dummy_canonical_identity_report_v31.json",
    )
