from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v18.domain_baselines import DomainBaselineForecastEngineV2
from predator_mesh.v18.domain_intelligence import DomainIntelligenceSpine
from predator_mesh.v18.integration import (
    V18BloodlineIntegration,
    V18DecisionLedgerIntegration,
    V18ForecastSnapshotIntegration,
    V18OutcomeLedgerIntegration,
)
from predator_mesh.v18.mission import DomainMissionScoreboard, DummyMissionStateV18
from predator_mesh.v18.research_packets import ResearchPacketFactory
from predator_mesh.v18.settlement import SettlementAmbiguityDetector, SettlementRuleMapper
from predator_mesh.v18.source_truth import SourceTruthRegistryV2

router = APIRouter(prefix="/api/v18", tags=["v18"])


@router.get("/domain-intelligence")
async def domain_intelligence() -> dict[str, Any]:
    spine = DomainIntelligenceSpine()
    return {
        "domain_intelligence": spine.to_report(),
        "profile_manifest": spine.profile_manifest(),
        "feature_schema": spine.feature_schema_report(),
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "proof_paths": [
            "artifacts/dummy/domain_intelligence_spine_report_v1.json",
            "artifacts/dummy/domain_profile_manifest_v1.json",
            "artifacts/dummy/domain_feature_schema_report_v1.json",
        ],
    }


@router.get("/research-packets")
async def research_packets() -> dict[str, Any]:
    factory = ResearchPacketFactory()
    return {
        "research_packets": factory.to_report(),
        "manifest": factory.manifest(),
        "no_trade_pressure": factory.no_trade_pressure_report(),
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "proof_paths": ["artifacts/dummy/research_packet_factory_report_v1.json"],
    }


@router.get("/evidence-stacks")
async def evidence_stacks() -> dict[str, Any]:
    factory = ResearchPacketFactory()
    return {
        "evidence_stacks": factory.evidence_stack_report(),
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "proof_paths": ["artifacts/dummy/evidence_stack_report_v1.json"],
    }


@router.get("/source-truth")
async def source_truth() -> dict[str, Any]:
    registry = SourceTruthRegistryV2()
    return {
        "source_truth": registry.to_report(),
        "legality": registry.legality_class_report(),
        "coverage": registry.domain_coverage_report(),
        "contradictions": registry.contradiction_report(),
        "promotion_eligibility": registry.promotion_eligibility_report(),
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "proof_paths": ["artifacts/dummy/source_truth_registry_v2_report.json"],
    }


@router.get("/domain-baselines")
async def domain_baselines() -> dict[str, Any]:
    engine = DomainBaselineForecastEngineV2()
    return {
        "domain_baselines": engine.to_report(),
        "snapshots": engine.snapshot_report(),
        "comparisons": engine.comparison_report(),
        "confidence_policy": engine.confidence_policy_report(),
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "proof_paths": ["artifacts/dummy/domain_baseline_forecast_engine_v2_report.json"],
    }


@router.get("/settlement-mapper")
async def settlement_mapper() -> dict[str, Any]:
    mapper = SettlementRuleMapper()
    return {
        "settlement_mapper": mapper.to_report(),
        "ambiguity_detector": SettlementAmbiguityDetector(mapper.profiles()).to_report(),
        "no_trade_pressure": mapper.no_trade_pressure_report(),
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "proof_paths": ["artifacts/dummy/settlement_rule_mapper_report_v1.json"],
    }


@router.get("/domain-scoreboard")
async def domain_scoreboard() -> dict[str, Any]:
    return {
        "domain_scoreboard": DomainMissionScoreboard().to_report(),
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "proof_paths": ["artifacts/dummy/domain_mission_scoreboard_report_v1.json"],
    }


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return {
        "mission_state": DummyMissionStateV18().to_report(),
        "outcome_ledger_integration": V18OutcomeLedgerIntegration().to_report(),
        "forecast_snapshot_integration": V18ForecastSnapshotIntegration().to_report(),
        "decision_ledger_integration": V18DecisionLedgerIntegration().to_report(),
        "bloodline_integration": V18BloodlineIntegration().to_report(),
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "proof_paths": ["artifacts/dummy/dummy_mission_state_report_v3.json"],
    }
