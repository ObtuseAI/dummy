"""Mesh health monitoring lane."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from predator_mesh.lanes.base import BaseLane
from predator_mesh.models import (
    LanePriority,
    MeshContext,
    MeshPriority,
    MeshResult,
    MeshTimeout,
)


class MeshHealthLane(BaseLane):
    """Detect stuck, slow, or noisy lanes from the shared proof ledger."""

    name = "mesh_health"
    priority = MeshPriority(level=LanePriority.MAINTENANCE)
    timeout = MeshTimeout(per_lane_timeout_s=5.0)

    async def execute(self, ctx: MeshContext) -> MeshResult:
        ledger = ctx.proof_ledger
        events = ledger.events if ledger is not None else []

        slow_lanes: list[str] = []
        stuck_lanes: list[str] = []
        lane_event_counts: dict[str, int] = defaultdict(int)

        for event in events:
            lane = event.get("lane") or "mesh"
            lane_event_counts[lane] += 1
            name = event.get("event", "")
            if name == "lane_timed_out":
                slow_lanes.append(lane)
            elif name in ("lane_quarantined", "lane_degraded"):
                stuck_lanes.append(lane)

        # A lane is noisy if it has contributed more than 20 ledger events.
        noisy_lanes = [
            lane for lane, count in lane_event_counts.items() if count > 20
        ]

        # Deduplicate while preserving order.
        slow_lanes = list(dict.fromkeys(slow_lanes))
        stuck_lanes = list(dict.fromkeys(stuck_lanes))

        report: dict[str, Any] = {
            "healthy": not (slow_lanes or stuck_lanes),
            "event_count": len(events),
            "slow_lanes": slow_lanes,
            "stuck_lanes": stuck_lanes,
            "noisy_lanes": noisy_lanes,
        }
        ctx.shared_state["mesh_health"] = report
        return self._complete(ctx, report, verdict="health_checked")
