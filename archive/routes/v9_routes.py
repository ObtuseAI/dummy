from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, status

from core.secret_guard import redact
from core.state import STATE
from predator_mesh.aggression.governor import ProofWeightedAggressionGovernor
from predator_mesh.data_inflow.adapters import MockDataAdapter
from predator_mesh.data_inflow.registry import DataSourceRegistry
from predator_mesh.data_inflow.scoring import SourceScorer
from predator_mesh.edge.engine import EdgeIntelligenceEngine
from predator_mesh.edge.models import MarketTerrainSnapshot
from predator_mesh.lane_registry import build_default_lanes
from predator_mesh.lanes.mesh_health import MeshHealthLane
from predator_mesh.models import (
    LaneState,
    MeshBudget,
    MeshContext,
    MeshResult,
    MeshRun,
    MeshTimeout,
)
from predator_mesh.proof_ledger import MeshProofLedger
from predator_mesh.scheduler import MeshScheduler
from predator_mesh.signals.normalizer import SignalNormalizer
from strategies.governor import CapImpact

router = APIRouter(prefix="/api/v9", tags=["v9"])

DASHBOARD_HANDLER_TIMEOUT_SECONDS = 25


async def _with_timeout(coro, timeout: float = DASHBOARD_HANDLER_TIMEOUT_SECONDS):
    """Await *coro* with a hard timeout; callers map timeout to a 503 response."""
    return await asyncio.wait_for(coro, timeout=timeout)


def _raise_timeout() -> None:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": "timeout",
            "message": f"Request exceeded {DASHBOARD_HANDLER_TIMEOUT_SECONDS}s timeout",
        },
    )


async def _discover_mock_candidates() -> list[Any]:
    """Return deterministic mock data-source candidates."""
    registry = DataSourceRegistry(scorer=SourceScorer())
    return await registry.discover([MockDataAdapter()])


async def _run_mesh_cycle(
    ledger: MeshProofLedger | None = None,
) -> tuple[MeshRun, MeshProofLedger]:
    """Run the default V9 mesh lanes and return the run plus its proof ledger."""
    scheduler = MeshScheduler(
        max_concurrency=5,
        default_timeout=MeshTimeout(
            per_lane_timeout_s=20.0,
            cycle_timeout_s=25.0,
            stuck_task_grace_s=2.0,
        ),
    )
    lanes = build_default_lanes()
    budget = MeshBudget(max_provider_calls=10, max_kalshi_calls=5)
    ledger = ledger or MeshProofLedger()
    run = await scheduler.run_cycle(
        lanes,
        budget,
        cycle_timeout=20.0,
        proof_ledger=ledger,
    )
    return run, ledger


def _lane_summary(result: MeshResult) -> dict[str, Any]:
    """Return a redacted, lightweight summary of a lane result."""
    duration: float | None = None
    if result.started_at and result.finished_at:
        duration = (result.finished_at - result.started_at).total_seconds()
    return {
        "lane_name": result.lane_name,
        "state": result.state.value,
        "error": result.error,
        "events_recorded": result.events_recorded,
        "duration_s": duration,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/mesh/status")
async def mesh_status() -> dict[str, Any]:
    try:
        run, _ledger = await _with_timeout(_run_mesh_cycle())
    except asyncio.TimeoutError:
        _raise_timeout()

    state_counts: dict[str, int] = {}
    for r in run.lane_results:
        state_counts[r.state.value] = state_counts.get(r.state.value, 0) + 1

    return redact(
        {
            "project": "Dummy",
            "milestone": "DUMMY_V9_CONCURRENT_PREDATOR_MESH",
            "mode": STATE.mode.value,
            "kill_switch_active": STATE.kill_switch.active,
            "emergency_stop_active": STATE.emergency_stop.active,
            "run_id": run.run_id,
            "state": run.state.value,
            "lane_count": len(run.lane_results),
            "lanes": [_lane_summary(r) for r in run.lane_results],
            "state_counts": state_counts,
            "budget": {
                "provider_calls_used": run.budget_used.provider_call_count,
                "kalshi_calls_used": run.budget_used.kalshi_call_count,
                "remaining_provider_calls": run.budget_used.remaining_provider_calls(),
                "remaining_kalshi_calls": run.budget_used.remaining_kalshi_calls(),
            },
            "proof_event_count": len(run.proof_refs),
            "stuck_task_count": len(run.stuck_tasks),
        }
    )


@router.get("/mesh/lanes")
async def mesh_lanes() -> dict[str, Any]:
    lanes = build_default_lanes()
    return redact(
        {
            "lane_count": len(lanes),
            "lanes": [
                {
                    "name": lane.name,
                    "priority": lane.priority.level.value,
                    "rank": lane.priority.rank,
                    "state": lane.state.value,
                    "timeout": lane.timeout.model_dump(),
                }
                for lane in lanes
            ],
        }
    )


@router.get("/data-inflow/sources")
async def data_inflow_sources() -> dict[str, Any]:
    try:
        discovered = await _with_timeout(_discover_mock_candidates(), timeout=15.0)
    except asyncio.TimeoutError:
        _raise_timeout()

    scorer = SourceScorer()
    source_scores = scorer.score_many(discovered)
    promoted = [c for c in discovered if c.status.value == "promoted"]
    pruned = [c for c in discovered if c.status.value == "pruned"]

    return redact(
        {
            "source_count": len(discovered),
            "promoted_count": len(promoted),
            "pruned_count": len(pruned),
            "sources": [
                {
                    **c.to_signal_input(),
                    "status": c.status.value,
                    "composite_score": (
                        c.score.get("composite_score") if isinstance(c.score, dict) else None
                    ),
                }
                for c in discovered
            ],
            "score_summary": [
                {
                    "source_id": s.source_id,
                    "composite_score": s.composite_score,
                    "tier": s.tier.value,
                }
                for s in source_scores
            ],
        }
    )


@router.get("/signals")
async def signals() -> dict[str, Any]:
    try:
        candidates = await _with_timeout(_discover_mock_candidates(), timeout=15.0)
    except asyncio.TimeoutError:
        _raise_timeout()

    normalizer = SignalNormalizer()
    signals = normalizer.normalize_many(candidates)
    actionable = sum(1 for s in signals if s.is_actionable())

    return redact(
        {
            "signal_count": len(signals),
            "actionable_signals": actionable,
            "signals": [s.model_dump() for s in signals],
        }
    )


@router.get("/edges")
async def edges() -> dict[str, Any]:
    try:
        candidates = await _with_timeout(_discover_mock_candidates(), timeout=15.0)
    except asyncio.TimeoutError:
        _raise_timeout()

    normalizer = SignalNormalizer()
    signals = normalizer.normalize_many(candidates)
    terrain = MarketTerrainSnapshot()
    engine = EdgeIntelligenceEngine()
    candidates_out = engine.score(signals, terrain)

    return redact(
        {
            "candidate_count": len(candidates_out),
            "terrain": terrain.model_dump(),
            "candidates": [c.to_manifest_entry() for c in candidates_out],
        }
    )


@router.get("/aggression-governor")
async def aggression_governor() -> dict[str, Any]:
    try:
        candidates = await _with_timeout(_discover_mock_candidates(), timeout=15.0)
    except asyncio.TimeoutError:
        _raise_timeout()

    scorer = SourceScorer()
    source_scores = scorer.score_many(candidates)

    normalizer = SignalNormalizer()
    signals = normalizer.normalize_many(candidates)
    terrain = MarketTerrainSnapshot()
    engine = EdgeIntelligenceEngine()
    edge_candidates = engine.score(signals, terrain)
    edge_candidate = edge_candidates[0] if edge_candidates else None

    governor = ProofWeightedAggressionGovernor()
    allocation = governor.allocate(
        edge_candidate=edge_candidate,
        source_scores=source_scores,
        forecast_confidence=0.65,
        model_agreement=0.80,
        calibration_support=0.60,
        liquidity_score=0.70,
        spread_score=0.75,
        settlement_risk_score=0.20,
        cap_impact=CapImpact(),
    )

    return redact(allocation.to_manifest_entry())


@router.get("/mesh-health")
async def mesh_health() -> dict[str, Any]:
    try:
        run, ledger = await _with_timeout(_run_mesh_cycle())
    except asyncio.TimeoutError:
        _raise_timeout()

    health_lane = MeshHealthLane()
    ctx = MeshContext(
        run_id=run.run_id,
        lane_name=health_lane.name,
        budget=MeshBudget(),
        timeout=MeshTimeout(per_lane_timeout_s=5.0),
        proof_ledger=ledger,
    )
    result = await health_lane.execute(ctx)
    report = result.result if result.result is not None else {}

    return redact(
        {
            "run_id": run.run_id,
            "run_state": run.state.value,
            "healthy": report.get("healthy"),
            "event_count": report.get("event_count"),
            "slow_lanes": report.get("slow_lanes", []),
            "stuck_lanes": report.get("stuck_lanes", []),
            "noisy_lanes": report.get("noisy_lanes", []),
        }
    )


@router.get("/proof")
async def proof() -> dict[str, Any]:
    try:
        run, ledger = await _with_timeout(_run_mesh_cycle())
    except asyncio.TimeoutError:
        _raise_timeout()

    return redact(
        {
            "run_id": run.run_id,
            "run_state": run.state.value,
            "report": ledger.to_report(),
        }
    )
