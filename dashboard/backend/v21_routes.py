from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v21.reports import V21ReportFactory

router = APIRouter(prefix="/api/v21", tags=["v21"])


def _reports() -> dict[str, dict[str, Any]]:
    return V21ReportFactory(enable_network=False).build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    return payload


@router.get("/source-activation-policy")
async def source_activation_policy() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "source_activation_policy": reports["source_activation_policy_report_v1.json"],
            "official_public_auto_approval": reports["official_public_auto_approval_policy_report_v1.json"],
            "key_required_policy": reports["key_required_source_policy_report_v1.json"],
            "licensed_commercial_policy": reports["licensed_commercial_source_policy_report_v1.json"],
            "sports_terms_strict_policy": reports["sports_terms_strict_policy_report_v1.json"],
        }
    )


@router.get("/source-approval-cockpit")
async def source_approval_cockpit() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "source_approval_cockpit": reports["source_approval_cockpit_report_v1.json"],
            "source_approval_queue": reports["source_approval_queue_report_v1.json"],
            "source_approval_operator_packet": reports["source_approval_operator_packet_v1.json"],
            "source_allowlist_delta": reports["source_allowlist_delta_recommendation_v1.json"],
        }
    )


@router.get("/official-public-activation")
async def official_public_activation() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "official_public_activation": reports["official_public_real_feed_activator_report_v1.json"],
            "feed_health": reports["official_public_feed_health_report_v1.json"],
            "evidence_manifest": reports["official_public_evidence_packet_manifest_v1.json"],
            "fallback_reasons": reports["official_public_fallback_reason_report_v1.json"],
        }
    )


@router.get("/eia-energy")
async def eia_energy() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "eia_energy": reports["eia_energy_real_adapter_v1_report.json"],
            "oil_inventory": reports["eia_oil_inventory_evidence_report_v1.json"],
            "evidence_packet": reports["eia_energy_evidence_packet_report_v1.json"],
            "source_blocker": reports["eia_energy_source_blocker_report_v1.json"],
        }
    )


@router.get("/nws-weather")
async def nws_weather() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "nws_weather": reports["nws_weather_real_adapter_v1_report.json"],
            "weather_evidence": reports["weather_official_evidence_packet_report_v1.json"],
            "weather_blocker": reports["weather_official_source_blocker_report_v1.json"],
            "oil_weather_disruption": reports["oil_weather_disruption_evidence_report_v1.json"],
        }
    )


@router.get("/crypto-public-exchange")
async def crypto_public_exchange() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "crypto_public_plan": reports["crypto_exchange_native_public_readonly_plan_report_v1.json"],
            "public_probe": reports["crypto_exchange_public_probe_report_v1.json"],
            "orderbook_evidence": reports["crypto_orderbook_public_evidence_report_v1.json"],
            "cross_exchange_divergence": reports["crypto_cross_exchange_divergence_evidence_report_v1.json"],
            "source_blocker": reports["crypto_exchange_source_blocker_report_v1.json"],
        }
    )


@router.get("/finance-macro-official")
async def finance_macro_official() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "finance_macro_official": reports["finance_macro_official_activation_v1_report.json"],
            "evidence_packet": reports["finance_macro_official_evidence_packet_report_v1.json"],
            "release_calendar": reports["macro_release_calendar_evidence_report_v1.json"],
            "source_blocker": reports["finance_official_source_blocker_report_v1.json"],
        }
    )


@router.get("/nasdaq-bootstrap")
async def nasdaq_bootstrap() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "nasdaq_bootstrap": reports["nasdaq_direction_bootstrap_v1_report.json"],
            "evidence_packet": reports["nasdaq_bootstrap_evidence_packet_report_v1.json"],
            "tier0_blocker": reports["nasdaq_tier0_blocker_report_v1.json"],
            "forecast_readiness_gate": reports["nasdaq_forecast_readiness_gate_report_v1.json"],
        }
    )


@router.get("/oil-bootstrap")
async def oil_bootstrap() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "oil_bootstrap": reports["oil_direction_bootstrap_v1_report.json"],
            "evidence_packet": reports["oil_bootstrap_evidence_packet_report_v1.json"],
            "tier0_blocker": reports["oil_tier0_blocker_report_v1.json"],
            "forecast_readiness_gate": reports["oil_forecast_readiness_gate_report_v1.json"],
        }
    )


@router.get("/licensed-acquisition")
async def licensed_acquisition() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "licensed_acquisition": reports["licensed_market_data_acquisition_planner_report_v1.json"],
            "vendor_capability_matrix": reports["vendor_capability_matrix_v1.json"],
            "operator_checklist": reports["operator_acquisition_checklist_v1.json"],
            "cost_benefit_scores": reports["source_cost_benefit_score_report_v1.json"],
        }
    )


@router.get("/github-miner")
async def github_miner() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "github_miner": reports["github_miner_live_bounded_upgrade_report_v1.json"],
            "live_search_probe": reports["github_live_search_probe_report_v1.json"],
            "rate_limit_state": reports["github_rate_limit_state_report_v1.json"],
            "repo_prioritizer": reports["github_repo_adapter_prioritizer_report_v1.json"],
        }
    )


@router.get("/evidence-router-v3")
async def evidence_router_v3() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "evidence_router_v3": reports["evidence_router_v3_report.json"],
            "evidence_role": reports["evidence_role_report_v1.json"],
            "evidence_sufficiency": reports["evidence_sufficiency_v2_report.json"],
            "evidence_route_truth": reports["evidence_route_truth_report_v1.json"],
        }
    )


@router.get("/forecast-pipeline-v3")
async def forecast_pipeline_v3() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "forecast_pipeline_v3": reports["forecast_pipeline_v3_report.json"],
            "evidence_sufficiency_gate": reports["forecast_evidence_sufficiency_gate_report_v1.json"],
            "context_only_blocker": reports["forecast_context_only_blocker_report_v1.json"],
            "edge_requirement": reports["forecast_edge_terrain_requirement_report_v1.json"],
        }
    )


@router.get("/compounding-v4")
async def compounding_v4() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "compounding_v4": reports["compounding_control_plane_v4_report.json"],
            "source_activation_queue": reports["source_activation_work_queue_report_v1.json"],
            "source_acquisition_queue": reports["source_acquisition_work_queue_report_v1.json"],
            "adapter_implementation_queue": reports["adapter_implementation_work_queue_report_v1.json"],
            "edge_terrain_improvement_queue": reports["edge_terrain_improvement_queue_report_v1.json"],
        }
    )


@router.get("/domain-scoreboard-v5")
async def domain_scoreboard_v5() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "domain_scoreboard_v5": reports["domain_scoreboard_v5_report.json"],
            "source_activation_breakout": reports["source_activation_breakout_scoreboard_v1.json"],
            "edge_readiness_by_domain": reports["edge_readiness_by_domain_report_v1.json"],
        }
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    reports = _reports()
    return _safe({"mission_state": reports["dummy_mission_state_report_v7.json"]})

