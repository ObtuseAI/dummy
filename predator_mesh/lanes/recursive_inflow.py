"""Recursive data inflow discovery lane."""

from __future__ import annotations

from typing import Any

from predator_mesh.data_inflow.adapters import (
    FileSampleAdapter,
    KalshiReadOnlyAdapter,
    MockDataAdapter,
    RSSSampleAdapter,
)
from predator_mesh.data_inflow.registry import DataSourceRegistry
from predator_mesh.data_inflow.scoring import SourceScorer
from predator_mesh.lanes.base import BaseLane
from predator_mesh.models import (
    LanePriority,
    LaneState,
    MeshContext,
    MeshPriority,
    MeshResult,
    MeshTimeout,
)


class RecursiveDataInflowLane(BaseLane):
    """Discover, score, and promote/prune data sources recursively.

    The lane uses deterministic sample/mock adapters and the read-only
    Kalshi adapter stub by default. No live orders are placed.
    """

    name = "recursive_inflow"
    priority = MeshPriority(level=LanePriority.SOURCE_DISCOVERY)
    timeout = MeshTimeout(per_lane_timeout_s=10.0)

    def __init__(
        self,
        adapters: list[Any] | None = None,
        registry: DataSourceRegistry | None = None,
    ) -> None:
        self.adapters = adapters or self._default_adapters()
        self.registry = registry or DataSourceRegistry(scorer=SourceScorer())

    def _default_adapters(self) -> list[Any]:
        """Return the default set of safe, read-only adapters."""
        return [
            MockDataAdapter(),
            RSSSampleAdapter(),
            FileSampleAdapter(),
            KalshiReadOnlyAdapter(),
        ]

    async def execute(self, ctx: MeshContext) -> MeshResult:
        try:
            discovered = await self.registry.discover(self.adapters)
            promoted = self.registry.promotion_engine.promote(discovered)
            pruned = self.registry.promotion_engine.prune(discovered)
            payload = {
                "sources_discovered": len(discovered),
                "sources_promoted": len(promoted),
                "sources_pruned": len(pruned),
                "candidates": [c.to_signal_input() for c in discovered],
            }
            ctx.shared_state["data_source_candidates"] = discovered
            return self._complete(ctx, payload, verdict="sources_scored")
        except Exception as exc:
            return self._fail(ctx, f"recursive inflow failed: {exc}", state=LaneState.DEGRADED)
