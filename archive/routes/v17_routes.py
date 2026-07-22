from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

from fastapi import APIRouter

from archive.report_scripts.generate_v17_reports import (
    generate_v17_report_bundle,
)

router = APIRouter(prefix="/api/v17", tags=["v17"])
_REPORT_CACHE_LOCK = threading.Lock()
_REPORT_CACHE_TTL_S = 5.0
_REPORT_CACHE: tuple[float, dict[str, dict[str, Any]]] | None = None


def _cached_reports() -> dict[str, dict[str, Any]]:
    # Every operational endpoint shares the fixture-free report builder.  A
    # locked, missing, or unqualified ledger therefore produces an explicit
    # INSUFFICIENT_DATA payload rather than falling back to KXDEMO rows.
    global _REPORT_CACHE
    now = time.monotonic()
    with _REPORT_CACHE_LOCK:
        if _REPORT_CACHE is not None and now - _REPORT_CACHE[0] <= _REPORT_CACHE_TTL_S:
            return _REPORT_CACHE[1]
        reports = generate_v17_report_bundle()
        _REPORT_CACHE = (time.monotonic(), reports)
        return reports


async def _reports() -> dict[str, dict[str, Any]]:
    return await asyncio.to_thread(_cached_reports)


@router.get("/outcome-ledger")
async def outcome_ledger() -> dict[str, Any]:
    reports = await _reports()
    return {
        "outcome_ledger": reports["outcome_ledger_report_v1.json"],
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/outcome_ledger_report_v1.json"],
    }


@router.get("/forecast-snapshots")
async def forecast_snapshots() -> dict[str, Any]:
    reports = await _reports()
    return {
        "forecast_snapshots": reports["forecast_snapshot_ledger_report_v1.json"],
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/forecast_snapshot_ledger_report_v1.json"],
    }


@router.get("/calibration")
async def calibration() -> dict[str, Any]:
    reports = await _reports()
    return {
        "calibration": reports["calibration_report_v1.json"],
        "drift": reports["calibration_drift_report_v1.json"],
        "domain_profiles": reports[
            "domain_calibration_profile_report_v1.json"
        ],
        "live_submit_disabled": True,
        "proof_paths": [
            "artifacts/dummy/calibration_report_v1.json",
            "artifacts/dummy/calibration_drift_report_v1.json",
            "artifacts/dummy/domain_calibration_profile_report_v1.json",
        ],
    }


@router.get("/outcome-attribution")
async def outcome_attribution() -> dict[str, Any]:
    reports = await _reports()
    return {
        "outcome_attribution": reports["outcome_attribution_report_v1.json"],
        "source_attribution": reports["source_attribution_report_v1.json"],
        "signal_attribution": reports["signal_attribution_report_v1.json"],
        "decision_attribution": reports["decision_attribution_report_v1.json"],
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/outcome_attribution_report_v1.json"],
    }


@router.get("/bloodline-truth")
async def bloodline_truth() -> dict[str, Any]:
    reports = await _reports()
    return {
        "source_bloodline": reports[
            "outcome_backed_source_bloodline_report_v1.json"
        ],
        "signal_bloodline": reports[
            "outcome_backed_signal_bloodline_report_v1.json"
        ],
        "truth_score": reports["bloodline_truth_score_report_v1.json"],
        "live_submit_disabled": True,
        "proof_paths": [
            "artifacts/dummy/outcome_backed_source_bloodline_report_v1.json",
            "artifacts/dummy/outcome_backed_signal_bloodline_report_v1.json",
        ],
    }


@router.get("/improvement-proposals")
async def improvement_proposals() -> dict[str, Any]:
    reports = await _reports()
    return {
        "improvement_proposals": reports[
            "improvement_proposal_factory_report_v1.json"
        ],
        "manifest": reports["improvement_proposal_manifest_v1.json"],
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/improvement_proposal_factory_report_v1.json"],
    }


@router.get("/domain-baselines")
async def domain_baselines() -> dict[str, Any]:
    reports = await _reports()
    return {
        "baseline_harness": reports["baseline_forecast_harness_report_v1.json"],
        "domain_baselines": reports["domain_baseline_forecast_report_v1.json"],
        "baseline_replay": reports["baseline_forecast_replay_report_v1.json"],
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/domain_baseline_forecast_report_v1.json"],
    }


@router.get("/outcome-observer")
async def outcome_observer() -> dict[str, Any]:
    reports = await _reports()
    return {
        "outcome_observer": reports["readonly_outcome_observer_report_v1.json"],
        "observation_modes": reports["outcome_observation_mode_report_v1.json"],
        "settlement_probe": reports["settlement_status_probe_report_v1.json"],
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/readonly_outcome_observer_report_v1.json"],
    }


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    reports = await _reports()
    return {
        "mission_state": reports["dummy_mission_state_report_v17.json"],
        "live_submit_disabled": True,
        "proof_paths": ["artifacts/dummy/dummy_mission_state_report_v17.json"],
    }

