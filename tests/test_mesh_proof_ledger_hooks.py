"""Tests that all mesh lanes record the expected proof ledger hooks.

Tests are split into:
- Lane-isolated tests: each lane is executed with the inputs it needs and a
  fresh ledger, so hook coverage is deterministic regardless of scheduler
  concurrency or lane ordering.
- Integration test: a full scheduler cycle with sequential execution and a
  custom inflow adapter that produces both promoted and pruned sources.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from core.ontology import Forecast, ForecastOpinion, OrderBook, OrderBookLevel
from predator_mesh.aggression.models import AggressionAllocation
from predator_mesh.budget import build_default_budget
from predator_mesh.data_inflow.adapters import (
    BaseDataAdapter,
    KalshiReadOnlyAdapter,
    MockDataAdapter,
)
from predator_mesh.data_inflow.models import DataSourceCandidate, SourceCategory
from predator_mesh.edge.engine import EdgeIntelligenceEngine
from predator_mesh.edge.models import MarketTerrainSnapshot
from predator_mesh.hybrid_router import MeshHybridRouter
from predator_mesh.lane_registry import LANE_REGISTRY, build_default_lanes
from predator_mesh.lanes.anomaly_mining import AnomalyMiningLane
from predator_mesh.lanes.calibration import CalibrationLane
from predator_mesh.lanes.firewall_rehearsal import FirewallRehearsalLane
from predator_mesh.lanes.forecast_update import ForecastUpdateLane
from predator_mesh.lanes.kalshi_terrain import KalshiTerrainLane
from predator_mesh.lanes.mesh_health import MeshHealthLane
from predator_mesh.lanes.recursive_inflow import RecursiveDataInflowLane
from predator_mesh.lanes.signal_normalization import SignalNormalizationLane
from predator_mesh.lanes.strategy_governor import StrategyGovernorLane
from predator_mesh.lanes.strategy_intelligence import StrategyIntelligenceLane
from predator_mesh.models import (
    LaneState,
    MeshContext,
    MeshPriority,
    MeshProofRef,
    MeshResult,
    MeshTimeout,
)
from predator_mesh.proof_ledger import MeshProofLedger
from predator_mesh.scheduler import MeshScheduler
from predator_mesh.signals.models import NormalizedSignal, SignalType
from strategies.governor import StrategyGovernor


class _PrunedMockAdapter(BaseDataAdapter):
    """Adapter that yields one promoted and one pruned candidate."""

    name = "pruned_mock"
    category = SourceCategory.MOCK
    adapter_type = "mock"

    async def fetch(self) -> list[DataSourceCandidate]:
        return [
            DataSourceCandidate(
                name="promoted_feed",
                category=SourceCategory.MOCK,
                adapter_type=self.adapter_type,
                reliability=1.0,
                freshness_s=0.0,
                latency_ms=1.0,
                uniqueness=1.0,
                edge_contribution=1.0,
            ),
            DataSourceCandidate(
                name="pruned_feed",
                category=SourceCategory.MOCK,
                adapter_type=self.adapter_type,
                reliability=0.0,
                freshness_s=9999.0,
                latency_ms=9999.0,
                uniqueness=0.0,
                edge_contribution=0.0,
            ),
        ]


def _ctx(lane_name: str, shared_state: dict | None = None) -> MeshContext:
    return MeshContext(
        run_id="ledger-test",
        lane_name=lane_name,
        budget=build_default_budget(),
        timeout=MeshTimeout(),
        proof_ledger=MeshProofLedger(),
        shared_state=shared_state or {},
    )


def _ctx_with_ledger(
    lane_name: str,
    ledger: MeshProofLedger,
    shared_state: dict | None = None,
) -> MeshContext:
    return MeshContext(
        run_id="ledger-test",
        lane_name=lane_name,
        budget=build_default_budget(),
        timeout=MeshTimeout(),
        proof_ledger=ledger,
        shared_state=shared_state or {},
    )


@pytest.mark.asyncio
async def test_kalshi_terrain_records_terrain_snapshot_and_no_secret() -> None:
    ctx = _ctx("kalshi_terrain")
    lane = KalshiTerrainLane(adapter=KalshiReadOnlyAdapter())
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert ctx.proof_ledger.has_event("terrain_snapshot", lane="kalshi_terrain")
    assert ctx.proof_ledger.has_event("no_secret_check", lane="kalshi_terrain")


@pytest.mark.asyncio
async def test_recursive_inflow_records_source_promotion_pruning_and_no_secret() -> None:
    ctx = _ctx("recursive_inflow")
    lane = RecursiveDataInflowLane(adapters=[_PrunedMockAdapter()])
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert ctx.proof_ledger.has_event("source_promoted", lane="recursive_inflow")
    assert ctx.proof_ledger.has_event("source_pruned", lane="recursive_inflow")
    assert ctx.proof_ledger.has_event("no_secret_check", lane="recursive_inflow")


@pytest.mark.asyncio
async def test_signal_normalization_records_signals_normalized_and_no_secret() -> None:
    candidate = DataSourceCandidate(
        name="feed",
        reliability=0.9,
        freshness_s=1.0,
        latency_ms=10.0,
        uniqueness=0.5,
        edge_contribution=0.5,
    )
    ctx = _ctx("signal_normalization", shared_state={"data_source_candidates": [candidate]})
    lane = SignalNormalizationLane()
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert ctx.proof_ledger.has_event("signals_normalized", lane="signal_normalization")
    assert ctx.proof_ledger.has_event("no_secret_check", lane="signal_normalization")


@pytest.mark.asyncio
async def test_anomaly_mining_records_edge_generated_and_no_secret() -> None:
    signals = [
        NormalizedSignal(
            signal_type=SignalType.PRICE_MOVE,
            strength=0.9,
            confidence=0.9,
            source_id="src-1",
        )
    ]
    ctx = _ctx("anomaly_mining", shared_state={"normalized_signals": signals})
    lane = AnomalyMiningLane()
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert ctx.proof_ledger.has_event("edge_generated", lane="anomaly_mining")
    assert ctx.proof_ledger.has_event("no_secret_check", lane="anomaly_mining")


@pytest.mark.asyncio
async def test_anomaly_mining_records_edge_rejected_for_noisy_signal() -> None:
    signals = [
        NormalizedSignal(
            signal_type=SignalType.PRICE_MOVE,
            strength=0.0,
            confidence=0.1,
            source_id="src-1",
        )
    ]
    ctx = _ctx("anomaly_mining", shared_state={"normalized_signals": signals})
    lane = AnomalyMiningLane()
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert ctx.proof_ledger.has_event("edge_rejected", lane="anomaly_mining")


@pytest.mark.asyncio
async def test_forecast_update_records_forecast_model_digest_and_no_secret() -> None:
    ledger = MeshProofLedger()
    ctx = _ctx_with_ledger("forecast_update", ledger)
    lane = ForecastUpdateLane(hybrid_router=MeshHybridRouter())
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert ledger.has_event("forecast_updated", lane="forecast_update")
    assert ledger.has_event("model_digest", lane="forecast_update")
    assert ledger.has_event("no_secret_check", lane="forecast_update")


@pytest.mark.asyncio
async def test_strategy_intelligence_records_strategy_evaluated_and_no_secret() -> None:
    ctx = _ctx("strategy_intelligence")
    lane = StrategyIntelligenceLane()
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert ctx.proof_ledger.has_event("strategy_evaluated", lane="strategy_intelligence")
    assert ctx.proof_ledger.has_event("no_secret_check", lane="strategy_intelligence")


@pytest.mark.asyncio
async def test_strategy_governor_records_governor_decision_and_no_secret() -> None:
    ctx = _ctx("strategy_governor")
    lane = StrategyGovernorLane(governor=StrategyGovernor())
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert ctx.proof_ledger.has_event("governor_decision", lane="strategy_governor")
    assert ctx.proof_ledger.has_event("no_secret_check", lane="strategy_governor")


@pytest.mark.asyncio
async def test_firewall_rehearsal_records_verdict_bypass_and_no_secret() -> None:
    ctx = _ctx("firewall_rehearsal")
    lane = FirewallRehearsalLane()
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert ctx.proof_ledger.has_event(
        "firewall_rehearsal_verdict", lane="firewall_rehearsal"
    )
    assert ctx.proof_ledger.has_event("no_order_bypass_check", lane="firewall_rehearsal")
    assert ctx.proof_ledger.has_event("no_secret_check", lane="firewall_rehearsal")


@pytest.mark.asyncio
async def test_calibration_records_calibration_scored_and_no_secret() -> None:
    ctx = _ctx("calibration")
    lane = CalibrationLane()
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert ctx.proof_ledger.has_event("calibration_scored", lane="calibration")
    assert ctx.proof_ledger.has_event("no_secret_check", lane="calibration")


@pytest.mark.asyncio
async def test_mesh_health_records_health_checked_and_no_secret() -> None:
    ledger = MeshProofLedger()
    ledger.record("lane_completed", lane="some_lane")
    ctx = _ctx_with_ledger("mesh_health", ledger)
    lane = MeshHealthLane()
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert ctx.proof_ledger.has_event("health_checked", lane="mesh_health")
    assert ctx.proof_ledger.has_event("no_secret_check", lane="mesh_health")


@pytest.mark.asyncio
async def test_base_lane_lifecycle_events_recorded() -> None:
    from predator_mesh.lanes.base import BaseLane

    class DummyLane(BaseLane):
        name = "dummy_lifecycle"
        priority = MeshPriority()

        async def execute(self, ctx: MeshContext) -> MeshResult:
            return self._complete(ctx, {"ok": True})

    ctx = _ctx("dummy_lifecycle")
    lane = DummyLane()
    result = await lane.execute(ctx)
    assert result.state == LaneState.COMPLETED
    assert ctx.proof_ledger.has_event("lane_completed", lane="dummy_lifecycle")


@pytest.mark.asyncio
async def test_proof_ledger_report_artifact_is_written(tmp_path: Path) -> None:
    ledger = MeshProofLedger()
    ledger.record("test_event", lane="test_lane", value=1)
    report_path = tmp_path / "mesh_proof_ledger_report_v1.json"
    written = ledger.write_report(path=report_path)
    assert written.exists()

    report = ledger.to_report()
    assert report["report_type"] == "mesh_proof_ledger_report_v1"
    assert report["event_count"] == len(ledger.events)
    assert "event_summary" in report
    assert "lane_summary" in report
    assert "events" in report


def test_proof_ledger_has_event_helper() -> None:
    ledger = MeshProofLedger()
    ledger.record("foo", lane="bar")
    assert ledger.has_event("foo", lane="bar")
    assert not ledger.has_event("baz", lane="bar")
    assert ledger.has_event("foo")


@pytest.mark.asyncio
async def test_default_scheduler_cycle_records_all_expected_hooks(
    tmp_path: Path,
) -> None:
    """Integration test: sequential scheduler cycle with deterministic inflow."""
    ledger = MeshProofLedger()
    scheduler = MeshScheduler(max_concurrency=1)
    budget = build_default_budget()

    from predator_mesh.models import LanePriority

    inflow = RecursiveDataInflowLane(adapters=[_PrunedMockAdapter()])
    inflow.priority = MeshPriority(level=LanePriority.REALTIME_MARKET_TERRAIN)

    lanes = [
        inflow,
        SignalNormalizationLane(),
        AnomalyMiningLane(),
        KalshiTerrainLane(),
        ForecastUpdateLane(hybrid_router=MeshHybridRouter()),
        StrategyIntelligenceLane(),
        StrategyGovernorLane(),
        FirewallRehearsalLane(),
        CalibrationLane(),
        MeshHealthLane(),
    ]

    run = await scheduler.run_cycle(
        lanes,
        budget,
        cycle_timeout=60.0,
        proof_ledger=ledger,
    )

    assert run.state.value in ("COMPLETED", "DEGRADED")
    recorded_events = {e.get("event") for e in ledger.events}
    expected = {
        "lane_started",
        "lane_completed",
        "source_promoted",
        "source_pruned",
        "signals_normalized",
        "edge_generated",
        "terrain_snapshot",
        "forecast_updated",
        "model_digest",
        "strategy_evaluated",
        "governor_decision",
        "firewall_rehearsal_verdict",
        "no_order_bypass_check",
        "calibration_scored",
        "health_checked",
        "no_secret_check",
    }
    missing = expected - recorded_events
    assert not missing, f"Missing expected proof ledger events: {missing}"


@pytest.mark.asyncio
async def test_ledger_events_contain_no_raw_prompts_or_secrets() -> None:
    ledger = MeshProofLedger()
    scheduler = MeshScheduler(max_concurrency=1)
    budget = build_default_budget()

    from predator_mesh.models import LanePriority

    inflow = RecursiveDataInflowLane(adapters=[_PrunedMockAdapter()])
    inflow.priority = MeshPriority(level=LanePriority.REALTIME_MARKET_TERRAIN)

    lanes = [
        inflow,
        SignalNormalizationLane(),
        AnomalyMiningLane(),
        KalshiTerrainLane(),
        ForecastUpdateLane(hybrid_router=MeshHybridRouter()),
        StrategyIntelligenceLane(),
        StrategyGovernorLane(),
        FirewallRehearsalLane(),
        CalibrationLane(),
        MeshHealthLane(),
    ]

    await scheduler.run_cycle(
        lanes,
        budget,
        cycle_timeout=60.0,
        proof_ledger=ledger,
    )

    secret_like = {"password", "token", "api_key", "private"}
    for event in ledger.events:
        for key, value in event.items():
            if key == "event":
                continue
            if isinstance(value, str):
                lowered = value.lower()
                for term in secret_like:
                    assert term not in lowered, (
                        f"Potential secret leak in {key}: {value!r}"
                    )
