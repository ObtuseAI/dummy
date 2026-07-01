"""Edge anomaly mining lane."""

from __future__ import annotations

from typing import Any

from predator_mesh.edge.engine import EdgeIntelligenceEngine
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


class AnomalyMiningLane(BaseLane):
    """Mine edge candidates from normalized signals and market terrain."""

    name = "anomaly_mining"
    priority = MeshPriority(level=LanePriority.HIGH_VALUE_SIGNAL)
    timeout = MeshTimeout(per_lane_timeout_s=10.0)

    def __init__(
        self,
        engine: EdgeIntelligenceEngine | None = None,
        terrain: MarketTerrainSnapshot | None = None,
    ) -> None:
        self.engine = engine or EdgeIntelligenceEngine()
        self.terrain = terrain or MarketTerrainSnapshot()

    async def execute(self, ctx: MeshContext) -> MeshResult:
        try:
            signals: list[Any] = ctx.shared_state.get("normalized_signals", [])
            if not signals:
                return self._complete(
                    ctx,
                    {"anomalies": [], "candidates": []},
                    verdict="no_signals",
                )
            candidates = self.engine.score(signals, self.terrain)
            payload = {
                "anomalies": [c.to_manifest_entry() for c in candidates],
                "candidates": [c.model_dump() for c in candidates],
            }
            ctx.shared_state["edge_candidates"] = candidates
            return self._complete(ctx, payload, verdict="candidates_scored")
        except Exception as exc:
            return self._fail(
                ctx,
                f"anomaly mining failed: {exc}",
                state=LaneState.DEGRADED,
            )
