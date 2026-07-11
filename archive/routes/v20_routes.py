from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v20.approval_gates import SourceApprovalGateV2, SourceCredentialRequirementReport, SourceLicenseGate, SourceTermsGate
from predator_mesh.v20.compounding import AutonomousCompoundingControlPlaneV3
from predator_mesh.v20.evidence_router import DomainEvidenceRouterV2, EvidencePriorityScore, EvidenceSufficiencyVerdict
from predator_mesh.v20.forecast_pipeline import EdgeAwareForecastPipelineV2, EdgeConfidencePolicy, EdgeNoTradeDecision
from predator_mesh.v20.github_source_miner import GitHubSourceMiner
from predator_mesh.v20.licensed_adapters import CommercialMarketDataGate, ExchangeNativeAdapterPlan, LicensedAdapterPlanPack, LicensedSourceReadiness
from predator_mesh.v20.mission import DummyMissionStateV6
from predator_mesh.v20.official_adapters import OfficialPublicAdapterActivationPack
from predator_mesh.v20.recommendations import SourceGapRecommendationEngine
from predator_mesh.v20.research_swarm import EdgeFocusedResearchSwarmV2
from predator_mesh.v20.scoreboard import DomainScoreboardV4
from predator_mesh.v20.source_universe import SourceUniverse
from predator_mesh.v20.terrain import CryptoDirectionTerrainStack, NasdaqDirectionTerrainStack, OilDirectionTerrainStack, SportsEdgeTerrainStack, WeatherEdgeTerrainStack

router = APIRouter(prefix="/api/v20", tags=["v20"])


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    return payload


@router.get("/source-universe")
async def source_universe() -> dict[str, Any]:
    universe = SourceUniverse()
    return _safe({"source_universe": universe.to_report(), "tier_matrix": universe.tier_matrix_report(), "edge_class": universe.edge_class_report()})


@router.get("/source-candidates")
async def source_candidates() -> dict[str, Any]:
    return _safe({"source_candidates": SourceUniverse().manifest_report()})


@router.get("/github-source-miner")
async def github_source_miner() -> dict[str, Any]:
    miner = GitHubSourceMiner()
    return _safe({"github_source_miner": miner.mine().to_report(), "candidate_manifest": miner.candidate_manifest(), "score_report": miner.score_report(), "adapter_plans": miner.adapter_plan_report()})


@router.get("/source-approval-gate")
async def source_approval_gate() -> dict[str, Any]:
    return _safe({"approval_gate": SourceApprovalGateV2().to_report(), "license_gate": SourceLicenseGate().to_report(), "terms_gate": SourceTermsGate().to_report(), "credential_requirements": SourceCredentialRequirementReport().to_report()})


@router.get("/official-public-adapters")
async def official_public_adapters() -> dict[str, Any]:
    return _safe({"official_public_adapters": OfficialPublicAdapterActivationPack().to_report()})


@router.get("/licensed-adapter-plans")
async def licensed_adapter_plans() -> dict[str, Any]:
    return _safe({"licensed_adapter_plans": LicensedAdapterPlanPack().to_report(), "exchange_native": ExchangeNativeAdapterPlan().to_report(), "commercial_gate": CommercialMarketDataGate().to_report(), "readiness": LicensedSourceReadiness().to_report()})


@router.get("/nasdaq-direction-terrain")
async def nasdaq_direction_terrain() -> dict[str, Any]:
    stack = NasdaqDirectionTerrainStack()
    return _safe({"terrain": stack.to_report(), "evidence": stack.evidence_packet_report(), "features": stack.edge_feature_map_report(), "no_trade": stack.no_trade_gate_report(), "blockers": stack.source_blocker_report()})


@router.get("/oil-direction-terrain")
async def oil_direction_terrain() -> dict[str, Any]:
    stack = OilDirectionTerrainStack()
    return _safe({"terrain": stack.to_report(), "evidence": stack.evidence_packet_report(), "features": stack.edge_feature_map_report(), "no_trade": stack.no_trade_gate_report(), "blockers": stack.source_blocker_report()})


@router.get("/crypto-direction-terrain")
async def crypto_direction_terrain() -> dict[str, Any]:
    stack = CryptoDirectionTerrainStack()
    return _safe({"terrain": stack.to_report(), "evidence": stack.evidence_packet_report(), "features": stack.edge_feature_map_report(), "no_trade": stack.no_trade_gate_report(), "blockers": stack.source_blocker_report()})


@router.get("/weather-terrain")
async def weather_terrain() -> dict[str, Any]:
    stack = WeatherEdgeTerrainStack()
    return _safe({"terrain": stack.to_report(), "evidence": stack.evidence_packet_report(), "features": stack.edge_feature_map_report(), "no_trade": stack.no_trade_gate_report()})


@router.get("/sports-terrain")
async def sports_terrain() -> dict[str, Any]:
    stack = SportsEdgeTerrainStack()
    return _safe({"terrain": stack.to_report(), "evidence": stack.evidence_packet_report(), "features": stack.edge_feature_map_report(), "no_trade": stack.no_trade_gate_report()})


@router.get("/evidence-router-v2")
async def evidence_router_v2() -> dict[str, Any]:
    return _safe({"evidence_router_v2": DomainEvidenceRouterV2().to_report(), "priority": EvidencePriorityScore().to_report(), "sufficiency": EvidenceSufficiencyVerdict().to_report()})


@router.get("/research-swarm-v2")
async def research_swarm_v2() -> dict[str, Any]:
    swarm = EdgeFocusedResearchSwarmV2()
    return _safe({"research_swarm_v2": swarm.to_report(), "task_manifest": swarm.task_manifest_report(), "source_gaps": swarm.source_gap_task_report(), "terrain_gaps": swarm.terrain_gap_task_report()})


@router.get("/forecast-pipeline-v2")
async def forecast_pipeline_v2() -> dict[str, Any]:
    pipeline = EdgeAwareForecastPipelineV2()
    return _safe({"forecast_pipeline_v2": pipeline.to_report(), "feature_contributions": pipeline.feature_contribution_report(), "confidence_policy": EdgeConfidencePolicy().to_report(), "no_trade_decisions": EdgeNoTradeDecision().to_report()})


@router.get("/source-gap-recommendations")
async def source_gap_recommendations() -> dict[str, Any]:
    engine = SourceGapRecommendationEngine()
    return _safe({"source_gap_recommendations": engine.to_report(), "priorities": engine.priority_report(), "acquisition_plan": engine.acquisition_plan_report(), "api_key_need": engine.api_key_need_report()})


@router.get("/compounding-control-plane-v3")
async def compounding_control_plane_v3() -> dict[str, Any]:
    plane = AutonomousCompoundingControlPlaneV3()
    return _safe({"compounding_control_plane_v3": plane.to_report(), "source_universe_work": plane.work_item_report("source_universe"), "edge_terrain_work": plane.work_item_report("edge_terrain"), "adapter_mining_work": plane.work_item_report("adapter_mining"), "forecast_improvement_work": plane.work_item_report("forecast_improvement")})


@router.get("/domain-scoreboard-v4")
async def domain_scoreboard_v4() -> dict[str, Any]:
    scoreboard = DomainScoreboardV4()
    return _safe({"domain_scoreboard_v4": scoreboard.to_report(), "coverage": scoreboard.coverage_scoreboard_report(), "readiness": scoreboard.readiness_scoreboard_report()})


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _safe({"mission_state": DummyMissionStateV6().to_report()})

