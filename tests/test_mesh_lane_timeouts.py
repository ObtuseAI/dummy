"""Tests for per-lane and cycle timeout behavior."""

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
    MeshScheduler,
    MeshTimeout,
)


class SlowLane(BaseLane):
    """Lane that sleeps longer than the per-lane timeout."""

    name = "slow"
    priority = MeshPriority(level=LanePriority.HIGH_VALUE_SIGNAL)

    async def execute(self, ctx: MeshContext) -> MeshResult:
        await asyncio.sleep(10.0)
        return self._complete(ctx, {"should_not_happen": True})


@pytest.mark.asyncio
async def test_per_lane_timeout_marks_lane_timed_out() -> None:
    scheduler = MeshScheduler(
        max_concurrency=1,
        default_timeout=MeshTimeout(
            per_lane_timeout_s=0.2,
            cycle_timeout_s=5.0,
            stuck_task_grace_s=0.1,
        ),
    )
    budget = build_default_budget()
    lanes = [SlowLane()]

    run = await scheduler.run_cycle(lanes, budget, cycle_timeout=5.0)

    assert len(run.lane_results) == 1
    result = run.lane_results[0]
    assert result.state == LaneState.TIMED_OUT
    assert result.error is not None
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_cycle_timeout_bounds_total_runtime() -> None:
    scheduler = MeshScheduler(
        max_concurrency=1,
        default_timeout=MeshTimeout(
            per_lane_timeout_s=20.0,
            cycle_timeout_s=30.0,
            stuck_task_grace_s=0.1,
        ),
    )
    budget = build_default_budget()
    lanes = [SlowLane() for _ in range(4)]

    start = time.monotonic()
    run = await scheduler.run_cycle(lanes, budget, cycle_timeout=0.3)
    elapsed = time.monotonic() - start

    # Cycle should finish quickly; allow a small margin for cleanup.
    assert elapsed < 1.0
    assert run.finished_at is not None
    assert all(r.state == LaneState.TIMED_OUT for r in run.lane_results)


@pytest.mark.asyncio
async def test_multiple_lanes_some_timeout() -> None:
    class MixedLane(BaseLane):
        def __init__(self, name: str, delay: float) -> None:
            super().__init__()
            self.name = name
            self.delay = delay

        async def execute(self, ctx: MeshContext) -> MeshResult:
            await asyncio.sleep(self.delay)
            return self._complete(ctx, {"name": self.name})

    scheduler = MeshScheduler(
        max_concurrency=2,
        default_timeout=MeshTimeout(
            per_lane_timeout_s=0.25,
            cycle_timeout_s=5.0,
            stuck_task_grace_s=0.1,
        ),
    )
    budget = build_default_budget()
    lanes = [
        MixedLane("quick", 0.05),
        MixedLane("slow", 0.5),
    ]

    run = await scheduler.run_cycle(lanes, budget, cycle_timeout=5.0)

    by_name = {r.lane_name: r for r in run.lane_results}
    assert by_name["quick"].state == LaneState.COMPLETED
    assert by_name["slow"].state == LaneState.TIMED_OUT
