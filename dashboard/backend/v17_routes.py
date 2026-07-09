from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter

from predator_mesh.v17.attribution import OutcomeAttributionEngine
from predator_mesh.v17.baselines import BaselineForecastHarness
from predator_mesh.v17.bloodlines import BloodlineTruthScore, OutcomeBackedSignalBloodline, OutcomeBackedSourceBloodline
from predator_mesh.v17.calibration import CalibrationEngine
from predator_mesh.v17.improvements import ImprovementProposalFactory
from predator_mesh.v17.mission_state import DummyMissionStateV17
from predator_mesh.v17.observer import ReadOnlyOutcomeObserver, SettlementStatusProbe
from scripts.generate_v17_reports import build_v17_context

router = APIRouter(prefix="/api/v17", tags=["v17"])


async def _context():
    return await asyncio.to_thread(build_v17_context)


@router.get("/outcome-ledger")
async def outcome_ledger() -> dict[str, Any]:
    context = await _context()
    return {
        "outcome_ledger": context.outcome_ledger.to_report(),
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/outcome_ledger_report_v1.json"],
    }


@router.get("/forecast-snapshots")
async def forecast_snapshots() -> dict[str, Any]:
    context = await _context()
    return {
        "forecast_snapshots": context.forecast_ledger.to_report(),
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/forecast_snapshot_ledger_report_v1.json"],
    }


@router.get("/calibration")
async def calibration() -> dict[str, Any]:
    context = await _context()
    engine = CalibrationEngine()
    return {
        "calibration": engine.to_report(context.forecasts, context.outcomes),
        "drift": engine.drift_report(context.forecasts, context.outcomes),
        "domain_profiles": engine.domain_profile(context.forecasts, context.outcomes).to_report(),
        "live_submit_disabled": True,
        "proof_paths": [
            "artifacts/dummy/calibration_report_v1.json",
            "artifacts/dummy/calibration_drift_report_v1.json",
            "artifacts/dummy/domain_calibration_profile_report_v1.json",
        ],
    }


@router.get("/outcome-attribution")
async def outcome_attribution() -> dict[str, Any]:
    context = await _context()
    engine = OutcomeAttributionEngine()
    return {
        "outcome_attribution": engine.to_report(context.forecasts, context.outcomes),
        "source_attribution": engine.source_attribution_report(context.forecasts, context.outcomes),
        "signal_attribution": engine.signal_attribution_report(context.forecasts, context.outcomes),
        "decision_attribution": engine.decision_attribution_report(context.decision_ledger.records, context.outcomes),
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/outcome_attribution_report_v1.json"],
    }


@router.get("/bloodline-truth")
async def bloodline_truth() -> dict[str, Any]:
    return {
        "source_bloodline": OutcomeBackedSourceBloodline().to_report(),
        "signal_bloodline": OutcomeBackedSignalBloodline().to_report(),
        "truth_score": BloodlineTruthScore(score=0.5, sample_count=2).to_dict(),
        "live_submit_disabled": True,
        "proof_paths": [
            "artifacts/dummy/outcome_backed_source_bloodline_report_v1.json",
            "artifacts/dummy/outcome_backed_signal_bloodline_report_v1.json",
        ],
    }


@router.get("/improvement-proposals")
async def improvement_proposals() -> dict[str, Any]:
    factory = ImprovementProposalFactory()
    return {
        "improvement_proposals": factory.to_report(),
        "manifest": factory.manifest(),
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/improvement_proposal_factory_report_v1.json"],
    }


@router.get("/domain-baselines")
async def domain_baselines() -> dict[str, Any]:
    harness = BaselineForecastHarness()
    return {
        "baseline_harness": harness.to_report(),
        "domain_baselines": harness.domain_forecast_report(),
        "baseline_replay": harness.replay_report(),
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/domain_baseline_forecast_report_v1.json"],
    }


@router.get("/outcome-observer")
async def outcome_observer() -> dict[str, Any]:
    observer = ReadOnlyOutcomeObserver()
    return {
        "outcome_observer": observer.to_report(),
        "observation_modes": ReadOnlyOutcomeObserver.mode_report(),
        "settlement_probe": SettlementStatusProbe().to_report(),
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/readonly_outcome_observer_report_v1.json"],
    }


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return {
        "mission_state": DummyMissionStateV17().to_report(),
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/dummy_mission_state_report_v17.json"],
    }

