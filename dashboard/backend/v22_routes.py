from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v22.reports import V22ReportFactory

router = APIRouter(prefix="/api/v22", tags=["v22"])


def _reports() -> dict[str, dict[str, Any]]:
    return V22ReportFactory(enable_network=False).build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    return payload


@router.get("/edge-role-classifier")
async def edge_role_classifier() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "edge_role_classifier": reports["edge_role_classifier_report_v1.json"],
            "evidence_role_classifier": reports["evidence_role_classifier_report_v1.json"],
            "edge_promotion_candidates": reports["edge_promotion_candidate_report_v1.json"],
            "context_only_blockers": reports["context_only_blocker_report_v1.json"],
        }
    )


@router.get("/evidence-normalizer")
async def evidence_normalizer() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "active_source_evidence_normalizer": reports["active_source_evidence_normalizer_report_v1.json"],
            "normalized_evidence_packet_manifest": reports["normalized_evidence_packet_manifest_v1.json"],
            "evidence_freshness_proof": reports["evidence_freshness_proof_report_v1.json"],
            "evidence_completeness_score": reports["evidence_completeness_score_report_v1.json"],
        }
    )


@router.get("/crypto-spot-edge")
async def crypto_spot_edge() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "crypto_spot_edge_terrain_activator": reports["crypto_spot_edge_terrain_activator_report_v1.json"],
            "crypto_spot_orderbook_terrain": reports["crypto_spot_orderbook_terrain_report_v1.json"],
            "crypto_cross_venue_comparison": reports["crypto_cross_venue_comparison_report_v1.json"],
            "crypto_spot_edge_readiness": reports["crypto_spot_edge_readiness_report_v1.json"],
            "crypto_spot_forecast_gate": reports["crypto_spot_forecast_gate_report_v1.json"],
        }
    )


@router.get("/weather-edge")
async def weather_edge() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "weather_edge_terrain_activator": reports["weather_edge_terrain_activator_report_v1.json"],
            "weather_forecast_edge_terrain": reports["weather_forecast_edge_terrain_report_v1.json"],
            "weather_settlement_station_mapper": reports["weather_settlement_station_mapper_report_v1.json"],
            "weather_forecast_readiness_gate": reports["weather_forecast_readiness_gate_report_v1.json"],
        }
    )


@router.get("/commodity-context-guard")
async def commodity_context_guard() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "commodity_context_guard": reports["commodity_context_guard_report_v1.json"],
            "oil_edge_insufficiency_reason": reports["oil_edge_insufficiency_reason_report_v1.json"],
            "commodity_source_upgrade_need": reports["commodity_source_upgrade_need_report_v1.json"],
        }
    )


@router.get("/finance-context-guard")
async def finance_context_guard() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "finance_context_guard": reports["finance_context_guard_report_v1.json"],
            "nasdaq_edge_insufficiency_reason": reports["nasdaq_edge_insufficiency_reason_report_v1.json"],
            "finance_source_upgrade_need": reports["finance_source_upgrade_need_report_v1.json"],
        }
    )


@router.get("/market-event-mapper")
async def market_event_mapper() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "market_event_mapper": reports["market_event_mapper_report_v1.json"],
            "evidence_market_link": reports["evidence_market_link_report_v1.json"],
            "market_class_candidate": reports["market_class_candidate_report_v1.json"],
            "market_mapping_blocker": reports["market_mapping_blocker_report_v1.json"],
        }
    )


@router.get("/kalshi-market-mapping")
async def kalshi_market_mapping() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "kalshi_market_discovery_recheck": reports["kalshi_market_discovery_recheck_v22_report.json"],
            "kalshi_domain_market_mapper": reports["kalshi_domain_market_mapper_report_v1.json"],
            "kalshi_market_evidence_join": reports["kalshi_market_evidence_join_report_v1.json"],
            "kalshi_market_mapping_blocker": reports["kalshi_market_mapping_blocker_report_v1.json"],
        }
    )


@router.get("/forecast-write-breakthrough")
async def forecast_write_breakthrough() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "forecast_write_breakthrough_engine": reports["forecast_write_breakthrough_engine_report_v1.json"],
            "forecast_write_candidate_manifest": reports["forecast_write_candidate_manifest_v1.json"],
            "forecast_write_decision": reports["forecast_write_decision_report_v1.json"],
            "forecast_snapshot_write_proof": reports["forecast_snapshot_write_proof_v1.json"],
            "no_trade_write_proof": reports["no_trade_write_proof_v1.json"],
        }
    )


@router.get("/outcome-observer-queue")
async def outcome_observer_queue() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "outcome_observer_queue": reports["outcome_observer_queue_v1_report.json"],
            "observer_check_plan": reports["observer_check_plan_report_v1.json"],
            "observer_queue_blocker": reports["observer_queue_blocker_report_v1.json"],
        }
    )


@router.get("/ledger-writes")
async def ledger_writes() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "v22_outcome_ledger_integration": reports["v22_outcome_ledger_integration_report_v1.json"],
            "forecast_snapshot_ledger_write": reports["forecast_snapshot_ledger_write_v22_report.json"],
            "no_trade_ledger_write": reports["no_trade_ledger_write_v22_report.json"],
            "observer_queue_ledger_write": reports["observer_queue_ledger_write_v22_report.json"],
            "ledger_write_integrity_check": reports["ledger_write_integrity_check_v22_report.json"],
        }
    )


@router.get("/edge-source-acquisition")
async def edge_source_acquisition() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "edge_source_acquisition_engine": reports["edge_source_acquisition_engine_v2_report.json"],
            "edge_source_acquisition_priority": reports["edge_source_acquisition_priority_report_v1.json"],
            "tier0_market_data_need": reports["tier0_market_data_need_report_v1.json"],
            "tier2_market_data_need": reports["tier2_market_data_need_report_v1.json"],
            "adapter_implementation_need": reports["adapter_implementation_need_report_v1.json"],
        }
    )


@router.get("/github-adapter-queue")
async def github_adapter_queue() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "github_adapter_implementation_queue": reports["github_adapter_implementation_queue_v2_report.json"],
            "adapter_candidate_work_item": reports["adapter_candidate_work_item_report_v1.json"],
            "adapter_risk_assessment": reports["adapter_risk_assessment_report_v1.json"],
            "adapter_test_plan": reports["adapter_test_plan_report_v1.json"],
        }
    )


@router.get("/compounding-v5")
async def compounding_v5() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "compounding_control_plane_v5": reports["compounding_control_plane_v5_report.json"],
            "forecast_write_improvement_queue": reports["forecast_write_improvement_queue_report_v1.json"],
            "edge_activation_improvement_queue": reports["edge_activation_improvement_queue_report_v1.json"],
            "source_acquisition_improvement_queue": reports["source_acquisition_improvement_queue_report_v1.json"],
            "next_tactical_bundle_selector": reports["next_tactical_bundle_selector_report_v1.json"],
        }
    )


@router.get("/domain-scoreboard-v6")
async def domain_scoreboard_v6() -> dict[str, Any]:
    reports = _reports()
    return _safe(
        {
            "domain_scoreboard_v6": reports["domain_scoreboard_v6_report.json"],
            "forecast_write_breakthrough_scoreboard": reports["forecast_write_breakthrough_scoreboard_v1.json"],
            "edge_terrain_activation_scoreboard": reports["edge_terrain_activation_scoreboard_v1.json"],
        }
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    reports = _reports()
    return _safe({"mission_state": reports["dummy_mission_state_report_v8.json"]})
