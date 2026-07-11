from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v19.bloodlines import SourceBloodlinePromotionV2
from predator_mesh.v19.calibration_bootstrap import RealEvidenceCalibrationBootstrap
from predator_mesh.v19.compounding import AutonomousCompoundingEngine
from predator_mesh.v19.forecast_activation import ForecastActivationEngine
from predator_mesh.v19.mission import DummyMissionStateV19
from predator_mesh.v19.outcome_observer import OutcomeObserverActivationV2
from predator_mesh.v19.research_ops import EvidenceModeSelector, EvidenceQualityScore, RealEvidenceResearchPacketBuilder
from predator_mesh.v19.scoreboard import DomainScoreboardV2
from predator_mesh.v19.source_activation import RealReadOnlySourceActivationController
from predator_mesh.v19.watchlist import DomainScanCycle, DomainWatchlist

router = APIRouter(prefix="/api/v19", tags=["v19"])


@router.get("/source-activation")
async def source_activation() -> dict[str, Any]:
    controller = RealReadOnlySourceActivationController()
    return {"source_activation": controller.to_report(), "candidate_manifest": controller.candidate_manifest(), "decisions": controller.decision_report(), "live_submit_disabled": True, "caps_unchanged": True}


@router.get("/domain-watchlist")
async def domain_watchlist() -> dict[str, Any]:
    return {"domain_watchlist": DomainWatchlist().to_report(), "live_submit_disabled": True, "caps_unchanged": True}


@router.get("/domain-scan-cycle")
async def domain_scan_cycle() -> dict[str, Any]:
    return {"domain_scan_cycle": DomainScanCycle().to_report(), "live_submit_disabled": True, "caps_unchanged": True}


@router.get("/real-evidence-packets")
async def real_evidence_packets() -> dict[str, Any]:
    return {"real_evidence_packets": RealEvidenceResearchPacketBuilder().to_report(), "mode_selector": EvidenceModeSelector().to_report(), "quality_score": EvidenceQualityScore().to_report(), "live_submit_disabled": True, "caps_unchanged": True}


@router.get("/forecast-activation")
async def forecast_activation() -> dict[str, Any]:
    engine = ForecastActivationEngine()
    return {"forecast_activation": engine.to_report(), "decisions": engine.decision_report(), "ledger_writes": engine.ledger_write_result_report(), "live_submit_disabled": True, "caps_unchanged": True}


@router.get("/outcome-observer-v2")
async def outcome_observer_v2() -> dict[str, Any]:
    observer = OutcomeObserverActivationV2()
    return {"outcome_observer_v2": observer.to_report(), "probe_plan": observer.probe_plan_report(), "resolution_decisions": observer.resolution_decision_report(), "live_submit_disabled": True, "caps_unchanged": True}


@router.get("/calibration-bootstrap")
async def calibration_bootstrap() -> dict[str, Any]:
    bootstrap = RealEvidenceCalibrationBootstrap()
    return {"calibration_bootstrap": bootstrap.to_report(), "mode_split": bootstrap.mode_split_report(), "domain_states": bootstrap.domain_state_report(), "live_submit_disabled": True, "caps_unchanged": True}


@router.get("/autonomous-compounding")
async def autonomous_compounding() -> dict[str, Any]:
    engine = AutonomousCompoundingEngine()
    return {"autonomous_compounding": engine.to_report(), "cycle": engine.cycle_report(), "proposals": engine.proposal_manifest(), "source_bloodlines": SourceBloodlinePromotionV2().to_report(), "live_submit_disabled": True, "caps_unchanged": True}


@router.get("/domain-scoreboard-v2")
async def domain_scoreboard_v2() -> dict[str, Any]:
    scoreboard = DomainScoreboardV2()
    return {"domain_scoreboard_v2": scoreboard.to_report(), "activation_matrix": scoreboard.activation_matrix_report(), "live_submit_disabled": True, "caps_unchanged": True}


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return {"mission_state": DummyMissionStateV19().to_report(), "live_submit_disabled": True, "caps_unchanged": True}
