"""Tests for the mesh lane registry."""

import pytest

from predator_mesh.lane_registry import (
    LANE_REGISTRY,
    AnomalyMiningLane,
    CalibrationLane,
    FirewallRehearsalLane,
    ForecastUpdateLane,
    KalshiTerrainLane,
    MeshHealthLane,
    RecursiveDataInflowLane,
    SignalNormalizationLane,
    StrategyGovernorLane,
    StrategyIntelligenceLane,
    build_default_lanes,
)
from predator_mesh.lanes.base import BaseLane


EXPECTED_LANES = {
    "kalshi_terrain": KalshiTerrainLane,
    "recursive_inflow": RecursiveDataInflowLane,
    "signal_normalization": SignalNormalizationLane,
    "anomaly_mining": AnomalyMiningLane,
    "forecast_update": ForecastUpdateLane,
    "strategy_intelligence": StrategyIntelligenceLane,
    "strategy_governor": StrategyGovernorLane,
    "firewall_rehearsal": FirewallRehearsalLane,
    "calibration": CalibrationLane,
    "mesh_health": MeshHealthLane,
}


def test_registry_contains_all_ten_lanes() -> None:
    assert len(LANE_REGISTRY) == 10
    for name, cls in EXPECTED_LANES.items():
        assert name in LANE_REGISTRY
        assert LANE_REGISTRY[name] is cls
        assert issubclass(cls, BaseLane)


def test_build_default_lanes_returns_ten_instances() -> None:
    lanes = build_default_lanes()
    assert len(lanes) == 10
    names = {lane.name for lane in lanes}
    assert names == set(EXPECTED_LANES)
    for lane in lanes:
        assert isinstance(lane, BaseLane)


@pytest.mark.asyncio
async def test_default_lanes_execute_without_error() -> None:
    """All default lane stubs should run to completion in isolation."""
    from predator_mesh.budget import build_default_budget
    from predator_mesh.models import MeshContext, MeshTimeout

    budget = build_default_budget()
    timeout = MeshTimeout()
    for lane in build_default_lanes():
        ctx = MeshContext(
            run_id="registry-test",
            lane_name=lane.name,
            budget=budget,
            timeout=timeout,
            proof_ledger=None,
        )
        result = await lane.execute(ctx)
        assert result.lane_name == lane.name
        assert result.state.value in ("COMPLETED", "BLOCKED")
