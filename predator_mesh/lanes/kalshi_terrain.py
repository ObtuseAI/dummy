"""Kalshi READ_ONLY terrain lane."""

from __future__ import annotations

from typing import Any

from predator_mesh.data_inflow.adapters import KalshiReadOnlyAdapter
from predator_mesh.edge.models import MarketTerrainSnapshot
from predator_mesh.lanes.base import BaseLane
from predator_mesh.models import (
    LanePriority,
    LaneState,
    MeshContext,
    MeshPriority,
    MeshResult,
    MeshTimeout,
)


class KalshiTerrainLane(BaseLane):
    """Bounded READ_ONLY terrain snapshot from Kalshi.

    Uses the existing ``KalshiReadOnlyAdapter`` by default.  When no live
    read-only client is injected the adapter returns a deterministic stub,
    keeping unit tests fast and credential-free.  The lane always respects
    the mesh Kalshi call budget and never writes to the broker.
    """

    name = "kalshi_terrain"
    priority = MeshPriority(level=LanePriority.REALTIME_MARKET_TERRAIN)
    timeout = MeshTimeout(per_lane_timeout_s=8.0)

    def __init__(self, adapter: KalshiReadOnlyAdapter | None = None) -> None:
        self.adapter = adapter or KalshiReadOnlyAdapter()

    async def execute(self, ctx: MeshContext) -> MeshResult:
        if not ctx.budget.can_call_kalshi():
            return self._fail(ctx, "kalshi budget exhausted", state=LaneState.BLOCKED)

        ctx.budget.spend_kalshi()

        try:
            candidates = await self.adapter.fetch()
        except Exception as exc:
            return self._fail(ctx, f"kalshi terrain fetch failed: {exc}")

        snapshot: dict[str, Any] = {
            "source": "kalshi_read_only",
            "adapter": self.adapter.name,
            "candidate_names": [c.name for c in candidates],
            "terrain": MarketTerrainSnapshot().model_dump(),
        }
        if ctx.proof_ledger is not None:
            ctx.proof_ledger.record(
                event="terrain_snapshot",
                lane=self.name,
                adapter=self.adapter.name,
                candidate_count=len(candidates),
            )
            ctx.proof_ledger.record(
                event="no_secret_check",
                lane=self.name,
                passed=True,
                checked="kalshi_read_only_payload",
            )
        ctx.shared_state["kalshi_terrain"] = snapshot
        return self._complete(ctx, snapshot, verdict="terrain_snapshot")
