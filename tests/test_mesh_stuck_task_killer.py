"""Tests for the stuck-task killer."""

from __future__ import annotations

import asyncio
import time

import pytest

from predator_mesh.budget import build_default_budget
from predator_mesh.lanes.base import BaseLane
from predator_mesh.models import (
    LanePriority,
    LaneState,
    MeshContext,
    MeshPriority,
    MeshResult,
    MeshTimeout,
)
from predator_mesh.scheduler import MeshScheduler


class StubbornLane(BaseLane):
    """Lane that ignores cancellation until an external stop event is set."""

    name = "stubborn"
    priority = MeshPriority(level=LanePriority.HIGH_VALUE_SIGNAL)

    def __init__(self, stop_event: asyncio.Event) -> None:
        super().__init__()
        self.stop_event = stop_event

    async def execute(self, ctx: MeshContext) -> MeshResult:
        while not self.stop_event.is_set():
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=0.05)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                continue
        return self._complete(ctx, {"stopped": True})


@pytest.mark.asyncio
async def test_stuck_task_is_quarantined_and_cycle_completes() -> None:
    stop_event = asyncio.Event()
    scheduler = MeshScheduler(
        max_concurrency=1,
        default_timeout=MeshTimeout(
            per_lane_timeout_s=0.15,
            cycle_timeout_s=5.0,
            stuck_task_grace_s=0.1,
        ),
    )
    budget = build_default_budget()
    lanes = [StubbornLane(stop_event)]

    start = time.monotonic()
    run = await scheduler.run_cycle(lanes, budget, cycle_timeout=5.0)
    elapsed = time.monotonic() - start

    assert elapsed < 1.0
    assert len(run.lane_results) == 1
    result = run.lane_results[0]
    assert result.state == LaneState.QUARANTINED
    assert run.state == LaneState.DEGRADED

    # Release the stuck lane so the test event loop can shut down cleanly.
    stop_event.set()
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_stuck_task_does_not_block_other_lanes() -> None:
    stop_event = asyncio.Event()

    class FastLane(BaseLane):
        name = "fast"
        priority = MeshPriority(level=LanePriority.HIGH_VALUE_SIGNAL)

        async def execute(self, ctx: MeshContext) -> MeshResult:
            await asyncio.sleep(0.05)
            return self._complete(ctx, {"ok": True})

    scheduler = MeshScheduler(
        max_concurrency=2,
        default_timeout=MeshTimeout(
            per_lane_timeout_s=0.15,
            cycle_timeout_s=5.0,
            stuck_task_grace_s=0.1,
        ),
    )
    budget = build_default_budget()
    lanes = [StubbornLane(stop_event), FastLane()]

    run = await scheduler.run_cycle(lanes, budget, cycle_timeout=5.0)

    by_name = {r.lane_name: r for r in run.lane_results}
    assert by_name["stubborn"].state == LaneState.QUARANTINED
    assert by_name["fast"].state == LaneState.COMPLETED

    stop_event.set()
    await asyncio.sleep(0.05)
