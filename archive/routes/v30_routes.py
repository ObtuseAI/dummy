from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v30.reports import V30ReportFactory

router = APIRouter(prefix="/api/v30", tags=["v30"])


def _reports() -> dict[str, dict[str, Any]]:
    return V30ReportFactory(enable_network=False).build()


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
    return _slice("dummy_mission_state_report_v16.json")


@router.get("/adapters")
async def adapters() -> dict[str, Any]:
    return _slice(
        "v30_adapter_implementation_selection_v1_report.json",
        "in_house_adapter_base_interface_v1_report.json",
        "weather_public_observation_adapter_v1_report.json",
        "crypto_public_price_adapter_v1_report.json",
        "public_event_reference_adapter_v1_report.json",
        "kalshi_readonly_rule_adapter_v1_report.json",
    )


@router.get("/fixtures")
async def fixtures() -> dict[str, Any]:
    return _slice(
        "adapter_fixture_contract_implementation_v1_report.json",
        "adapter_fixture_record_v1_report.json",
        "adapter_fixture_loader_v1_report.json",
        "adapter_fixture_validator_v1_report.json",
        "adapter_fixture_mode_guard_v1_report.json",
    )


@router.get("/normalization")
async def normalization() -> dict[str, Any]:
    return _slice(
        "adapter_normalization_pipeline_v1_report.json",
        "normalized_adapter_evidence_v1_report.json",
        "adapter_evidence_quality_gate_v1_report.json",
        "adapter_freshness_gate_v1_report.json",
        "adapter_metric_compatibility_gate_v1_report.json",
    )


@router.get("/settlement")
async def settlement() -> dict[str, Any]:
    return _slice(
        "adapter_to_settlement_compatibility_v1_report.json",
        "adapter_settlement_join_candidate_v1_report.json",
        "adapter_settlement_join_decision_v1_report.json",
        "adapter_settlement_confidence_v1_report.json",
        "adapter_settlement_blocker_v1_report.json",
    )


@router.get("/closure-dry-run")
async def closure_dry_run() -> dict[str, Any]:
    return _slice(
        "adapter_observation_closure_dry_run_v1_report.json",
        "adapter_observation_closure_candidate_v1_report.json",
        "adapter_observation_closure_decision_v1_report.json",
        "adapter_observation_closure_score_eligibility_v1_report.json",
        "adapter_observation_closure_blocker_v1_report.json",
    )


@router.get("/probe-readiness")
async def probe_readiness() -> dict[str, Any]:
    return _slice(
        "public_probe_implementation_readiness_v3_report.json",
        "adapter_public_probe_ready_candidate_v1_report.json",
        "adapter_public_probe_endpoint_readiness_v1_report.json",
        "adapter_public_probe_runtime_readiness_v1_report.json",
        "adapter_public_probe_safety_readiness_v1_report.json",
        "adapter_public_probe_readiness_blocker_v1_report.json",
    )


@router.get("/sports")
async def sports() -> dict[str, Any]:
    return _slice(
        "sports_fixture_only_adapter_guard_v1_report.json",
        "sports_fixture_only_adapter_state_v1_report.json",
        "sports_live_source_approval_requirement_v1_report.json",
        "sports_terms_blocked_adapter_decision_v1_report.json",
        "sports_fixture_only_evidence_guard_v1_report.json",
    )


@router.get("/source-truth")
async def source_truth() -> dict[str, Any]:
    return _slice(
        "adapter_source_truth_v11_report.json",
        "adapter_implementation_truth_signal_v1_report.json",
        "adapter_fixture_truth_signal_v1_report.json",
        "adapter_normalization_truth_signal_v1_report.json",
        "adapter_settlement_truth_signal_v1_report.json",
        "adapter_implementation_partial_reduction_v1_report.json",
        "adapter_to_observation_compounding_control_plane_v14_report.json",
        "domain_market_class_scoreboard_v15_report.json",
    )


@router.get("/safety")
async def safety() -> dict[str, Any]:
    return _slice(
        "no_secret_leak_report_v30.json",
        "no_source_api_key_leak_report_v30.json",
        "no_github_token_leak_report_v30.json",
        "no_direct_order_bypass_report_v30.json",
        "no_direct_cancel_bypass_report_v30.json",
        "no_browser_automation_report_v30.json",
        "no_pageagent_report_v30.json",
        "no_dom_extraction_report_v30.json",
        "no_mined_repo_clone_report_v30.json",
        "no_mined_repo_import_report_v30.json",
        "no_mined_repo_execution_report_v30.json",
        "no_adapter_implementation_to_execution_bridge_report_v30.json",
        "no_adapter_fixture_scored_live_report_v30.json",
        "no_adapter_dry_run_scored_live_report_v30.json",
        "blunder_separation_recheck_v30.json",
        "dummy_canonical_identity_report_v30.json",
    )
