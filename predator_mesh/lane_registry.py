"""Registry of all mesh lanes."""

from __future__ import annotations

from typing import Any

from predator_mesh.lanes.anomaly_mining import AnomalyMiningLane
from predator_mesh.lanes.base import BaseLane
from predator_mesh.lanes.recursive_inflow import RecursiveDataInflowLane
from predator_mesh.lanes.signal_normalization import SignalNormalizationLane
from predator_mesh.models import (
    LanePriority,
    LaneState,
    MeshContext,
    MeshPriority,
    MeshResult,
    MeshTimeout,
)


class KalshiTerrainLane(BaseLane):
    """Kalshi READ_ONLY terrain lane."""

    name = "kalshi_terrain"
    priority = MeshPriority(level=LanePriority.REALTIME_MARKET_TERRAIN)
    timeout = MeshTimeout(per_lane_timeout_s=8.0)

    async def execute(self, ctx: MeshContext) -> MeshResult:
        if not ctx.budget.can_call_kalshi():
            return self._fail(ctx, "kalshi budget exhausted", state=LaneState.BLOCKED)
        ctx.budget.spend_kalshi()
        return self._complete(ctx, {"terrain": "market_snapshot_stub"})


class ForecastUpdateLane(BaseLane):
    """Hybrid forecast update lane."""

    name = "forecast_update"
    priority = MeshPriority(level=LanePriority.FORECAST_UPDATE)
    timeout = MeshTimeout(per_lane_timeout_s=18.0)

    async def execute(self, ctx: MeshContext) -> MeshResult:
        if not ctx.budget.can_call_provider():
            return self._fail(ctx, "provider budget exhausted", state=LaneState.BLOCKED)
        ctx.budget.spend_provider()
        return self._complete(ctx, {"forecasts": []})


class StrategyIntelligenceLane(BaseLane):
    """Strategy family execution lane."""

    name = "strategy_intelligence"
    priority = MeshPriority(level=LanePriority.STRATEGY_REVIEW)
    timeout = MeshTimeout(per_lane_timeout_s=12.0)

    async def execute(self, ctx: MeshContext) -> MeshResult:
        return self._complete(ctx, {"strategies": []})


class StrategyGovernorLane(BaseLane):
    """Strategy governor routing lane."""

    name = "strategy_governor"
    priority = MeshPriority(level=LanePriority.STRATEGY_REVIEW)
    timeout = MeshTimeout(per_lane_timeout_s=10.0)

    async def execute(self, ctx: MeshContext) -> MeshResult:
        return self._complete(ctx, {"governor_decisions": []})


class FirewallRehearsalLane(BaseLane):
    """Live Broker Firewall rehearsal lane."""

    name = "firewall_rehearsal"
    priority = MeshPriority(level=LanePriority.CALIBRATION_UPDATE)
    timeout = MeshTimeout(per_lane_timeout_s=6.0)

    async def execute(self, ctx: MeshContext) -> MeshResult:
        return self._complete(
            ctx, {"rehearsal": "blocked_until_live_submit_enabled"}
        )


class CalibrationLane(BaseLane):
    """Forecast/source calibration lane."""

    name = "calibration"
    priority = MeshPriority(level=LanePriority.CALIBRATION_UPDATE)
    timeout = MeshTimeout(per_lane_timeout_s=8.0)

    async def execute(self, ctx: MeshContext) -> MeshResult:
        return self._complete(ctx, {"calibration_updates": []})


class MeshHealthLane(BaseLane):
    """Mesh health monitoring lane."""

    name = "mesh_health"
    priority = MeshPriority(level=LanePriority.MAINTENANCE)
    timeout = MeshTimeout(per_lane_timeout_s=5.0)

    async def execute(self, ctx: MeshContext) -> MeshResult:
        return self._complete(ctx, {"healthy": True})


LANE_REGISTRY: dict[str, type[BaseLane]] = {
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


def build_default_lanes() -> list[BaseLane]:
    """Instantiate one of each registered lane."""
    return [lane_cls() for lane_cls in LANE_REGISTRY.values()]
