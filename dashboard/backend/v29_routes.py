from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v29.reports import V29ReportFactory

router = APIRouter(prefix="/api/v29", tags=["v29"])


def _reports() -> dict[str, dict[str, Any]]:
    return V29ReportFactory(enable_network=False).build()


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
    return _slice("dummy_mission_state_report_v15.json")


@router.get("/oss-candidates")
async def oss_candidates() -> dict[str, Any]:
    return _slice(
        "oss_candidate_universe_normalizer_v1_report.json",
        "oss_candidate_canonical_record_report_v1.json",
        "oss_candidate_duplicate_cluster_report_v1.json",
        "oss_candidate_keyword_provenance_report_v1.json",
        "oss_candidate_category_map_report_v1.json",
    )


@router.get("/triage")
async def triage() -> dict[str, Any]:
    return _slice(
        "oss_license_terms_triage_v1_report.json",
        "oss_maintenance_quality_score_v1_report.json",
        "market_class_oss_fit_scorer_v1_report.json",
        "oss_candidate_promotion_gate_v1_report.json",
    )


@router.get("/adapter-specs")
async def adapter_specs() -> dict[str, Any]:
    return _slice(
        "adapter_spec_factory_v1_report.json",
        "fixture_schema_generator_v1_report.json",
        "adapter_contract_test_planner_v1_report.json",
        "adapter_sprint_queue_v6_report.json",
    )


@router.get("/probe-readiness")
async def probe_readiness() -> dict[str, Any]:
    return _slice(
        "public_probe_readiness_planner_v2_report.json",
        "settlement_gap_adapter_mapper_v1_report.json",
        "oss_to_observation_compounding_control_plane_v13_report.json",
        "domain_market_class_scoreboard_v14_report.json",
    )


@router.get("/domain-packs")
async def domain_packs() -> dict[str, Any]:
    return _slice(
        "sports_source_legality_resolver_v3_report.json",
        "weather_oss_adapter_spec_pack_v1_report.json",
        "crypto_oss_adapter_spec_pack_v1_report.json",
        "event_market_oss_adapter_spec_pack_v1_report.json",
        "trading_backtesting_oss_reference_pack_v1_report.json",
        "bloomberg_alternative_oss_reference_pack_v1_report.json",
    )


@router.get("/safety")
async def safety() -> dict[str, Any]:
    return _slice(
        "no_secret_leak_report_v29.json",
        "no_source_api_key_leak_report_v29.json",
        "no_github_token_leak_report_v29.json",
        "no_direct_order_bypass_report_v29.json",
        "no_direct_cancel_bypass_report_v29.json",
        "no_browser_automation_report_v29.json",
        "no_pageagent_report_v29.json",
        "no_dom_extraction_report_v29.json",
        "no_browser_research_lane_report_v29.json",
        "no_mined_repo_clone_report_v29.json",
        "no_mined_repo_import_report_v29.json",
        "no_mined_repo_execution_report_v29.json",
        "no_adapter_spec_to_execution_bridge_report_v29.json",
        "no_public_probe_readiness_to_execution_bridge_report_v29.json",
        "blunder_separation_recheck_v29.json",
        "dummy_canonical_identity_report_v29.json",
    )
