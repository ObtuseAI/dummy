"""Tests for the bounded concurrent mesh scheduler."""

from __future__ import annotations

import asyncio

import pytest

from predator_mesh.budget import build_default_budget
from predator_mesh.lane_registry import build_default_lanes
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


class FastLane(BaseLane):
    """Lane that completes quickly with a small payload."""

    name = "fast"
    priority = MeshPriority(level=LanePriority.HIGH_VALUE_SIGNAL)

    async def execute(self, ctx: MeshContext) -> MeshResult:
        await asyncio.sleep(0.05)
        return self._complete(ctx, {"ok": True})


@pytest.mark.asyncio
async def test_scheduler_cycle_completes_with_default_lanes() -> None:
    scheduler = MeshScheduler(max_concurrency=3)
    budget = build_default_budget()
    lanes = build_default_lanes()
    run = await scheduler.run_cycle(
        lanes,
        budget,
        cycle_timeout=10.0,
    )

    assert run.state == LaneState.COMPLETED
    assert len(run.lane_results) == len(lanes)
    assert all(r.state == LaneState.COMPLETED for r in run.lane_results)
    assert run.finished_at is not None
    assert run.started_at <= run.finished_at


@pytest.mark.asyncio
async def test_scheduler_respects_max_concurrency() -> None:
    lock = asyncio.Lock()
    active = 0
    max_active = 0

    class CountingLane(BaseLane):
        name = "counting"
        priority = MeshPriority(level=LanePriority.HIGH_VALUE_SIGNAL)

        async def execute(self, ctx: MeshContext) -> MeshResult:
            nonlocal active, max_active
            async with lock:
                active += 1
                max_active = max(max_active, active)
            await asyncio.sleep(0.15)
            async with lock:
                active -= 1
            return self._complete(ctx, {"done": True})

    scheduler = MeshScheduler(max_concurrency=2)
    budget = build_default_budget()
    lanes = [CountingLane() for _ in range(5)]

    run = await scheduler.run_cycle(lanes, budget, cycle_timeout=5.0)

    assert max_active <= 2
    assert all(r.state == LaneState.COMPLETED for r in run.lane_results)


@pytest.mark.asyncio
async def test_scheduler_sorts_by_priority() -> None:
    """Higher-priority lanes should start before lower-priority ones.

    We use a tiny semaphore so ordering is observable: only one lane runs at a
    time and we record the order of execution.
    """
    order: list[str] = []

    class PriorityLane(BaseLane):
        def __init__(self, name: str, level: LanePriority) -> None:
            super().__init__()
            self.name = name
            self.priority = MeshPriority(level=level)

        async def execute(self, ctx: MeshContext) -> MeshResult:
            order.append(self.name)
            await asyncio.sleep(0.01)
            return self._complete(ctx, {"name": self.name})

    scheduler = MeshScheduler(max_concurrency=1)
    budget = build_default_budget()
    lanes = [
        PriorityLane("maintenance", LanePriority.MAINTENANCE),
        PriorityLane("high", LanePriority.HIGH_VALUE_SIGNAL),
        PriorityLane("realtime", LanePriority.REALTIME_MARKET_TERRAIN),
    ]

    await scheduler.run_cycle(lanes, budget, cycle_timeout=5.0)

    assert order == ["realtime", "high", "maintenance"]


@pytest.mark.asyncio
async def test_budget_tracks_provider_and_kalshi_calls() -> None:
    scheduler = MeshScheduler(max_concurrency=5)
    budget = build_default_budget(max_provider_calls=5, max_kalshi_calls=2)
    lanes = build_default_lanes()

    run = await scheduler.run_cycle(lanes, budget, cycle_timeout=10.0)

    assert run.budget_used.provider_call_count > 0
    assert run.budget_used.kalshi_call_count > 0
    assert run.budget_used.provider_call_count <= budget.max_provider_calls
    assert run.budget_used.kalshi_call_count <= budget.max_kalshi_calls
