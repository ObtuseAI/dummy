from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v28.reports import V28ReportFactory

router = APIRouter(prefix="/api/v28", tags=["v28"])


def _reports() -> dict[str, dict[str, Any]]:
    return V28ReportFactory(enable_network=False).build()


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
    return _slice("dummy_mission_state_report_v14.json")


@router.get("/integration-gate")
async def integration_gate() -> dict[str, Any]:
    return _slice(
        "explicit_integration_mode_gate_v2_report.json",
        "integration_mode_intent_report_v1.json",
        "integration_mode_environment_gate_report_v1.json",
        "integration_mode_operator_proof_report_v1.json",
        "integration_mode_runtime_scope_report_v1.json",
        "integration_mode_default_disabled_proof_report_v1.json",
        "integration_mode_config_diff_guard_report_v1.json",
    )


@router.get("/public-probes")
async def public_probes() -> dict[str, Any]:
    return _slice(
        "public_probe_runner_v2_report.json",
        "public_probe_run_plan_report_v1.json",
        "public_probe_run_task_report_v1.json",
        "public_probe_run_result_report_v1.json",
        "public_probe_run_budget_report_v1.json",
        "public_probe_run_failure_report_v1.json",
        "public_probe_run_redaction_proof_report_v1.json",
    )


@router.get("/observation-closure")
async def observation_closure() -> dict[str, Any]:
    return _slice(
        "cached_public_probe_evidence_ingestion_v1_report.json",
        "observation_evidence_normalizer_v1_report.json",
        "settlement_rule_disambiguation_engine_v2_report.json",
        "source_unavailable_recovery_engine_v1_report.json",
        "due_forecast_observation_closure_v3_report.json",
        "live_score_seed_engine_v1_report.json",
        "live_calibration_seed_engine_v1_report.json",
    )


@router.get("/sports")
async def sports() -> dict[str, Any]:
    return _slice(
        "sports_public_source_decision_engine_v2_report.json",
        "sports_source_decision_candidate_report_v1.json",
        "sports_terms_evidence_record_report_v1.json",
        "sports_source_decision_report_v1.json",
        "sports_source_mode_decision_report_v1.json",
        "sports_source_decision_blocker_report_v1.json",
    )


@router.get("/oss-gap-fill")
async def oss_gap_fill() -> dict[str, Any]:
    return _slice(
        "open_source_github_gap_fill_accelerator_v1_report.json",
        "github_repo_candidate_manifest_v2_report.json",
        "github_repo_domain_classification_v1_report.json",
        "domain_gap_to_repo_map_v1_report.json",
        "sports_open_source_terms_classifier_v1_report.json",
        "bloomberg_open_source_legality_gate_v1_report.json",
        "crypto_open_source_public_adapter_plan_v1_report.json",
        "trading_repo_execution_safety_classifier_v1_report.json",
    )


@router.get("/safety")
async def safety() -> dict[str, Any]:
    return _slice(
        "no_secret_leak_report_v28.json",
        "no_source_api_key_leak_report_v28.json",
        "no_github_token_leak_report_v28.json",
        "no_direct_order_bypass_report_v28.json",
        "no_direct_cancel_bypass_report_v28.json",
        "no_github_repo_code_execution_report_v28.json",
        "no_open_source_gap_fill_to_execution_bridge_report_v28.json",
        "no_public_probe_runner_to_execution_bridge_report_v28.json",
        "no_observation_closure_to_execution_bridge_report_v28.json",
        "blunder_separation_recheck_v28.json",
        "dummy_canonical_identity_report_v28.json",
    )
