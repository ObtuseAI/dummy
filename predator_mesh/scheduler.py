"""Bounded concurrent mesh scheduler with per-lane and cycle timeouts."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from predator_mesh.models import (
    LaneState,
    MeshBudget,
    MeshContext,
    MeshHeartbeat,
    MeshLane,
    MeshProofRef,
    MeshResult,
    MeshRun,
    MeshTimeout,
)
from predator_mesh.proof_ledger import MeshProofLedger


class MeshScheduler:
    """Run mesh lanes with bounded concurrency and timeout guards.

    - Lanes are sorted by priority (highest first).
    - A semaphore caps the number of lanes running at once.
    - Each lane is wrapped in ``asyncio.wait_for`` for per-lane timeout.
    - The lane task is shielded so the scheduler can attempt graceful
      cancellation; if the lane refuses to cancel within the grace window,
      it is marked ``QUARANTINED`` and the cycle continues.
    - The entire cycle is bounded by ``cycle_timeout``.
    """

    def __init__(
        self,
        max_concurrency: int = 5,
        default_timeout: MeshTimeout | None = None,
    ) -> None:
        self.max_concurrency = max(max_concurrency, 1)
        self.default_timeout = default_timeout or MeshTimeout()

    async def run_cycle(
        self,
        lanes: list[Any],
        budget: MeshBudget,
        cycle_timeout: float | None = None,
    ) -> MeshRun:
        """Execute ``lanes`` under the given ``budget`` and return a ``MeshRun``."""
        timeout = self.default_timeout
        if cycle_timeout is not None:
            timeout = timeout.model_copy(update={"cycle_timeout_s": cycle_timeout})

        run_id = str(uuid4())
        ledger = MeshProofLedger()
        run = MeshRun(run_id=run_id, budget_used=budget, timeouts=[timeout])
        shared_state: dict[str, Any] = {}

        semaphore = asyncio.Semaphore(self.max_concurrency)
        # Sort by priority rank descending.
        ordered = sorted(
            lanes,
            key=lambda lane: getattr(lane, "priority", MeshLane(name="").priority).rank,
            reverse=True,
        )

        async def _run_lane(lane: Any) -> MeshResult:
            async with semaphore:
                return await self._execute_lane(
                    lane=lane,
                    budget=budget,
                    timeout=timeout,
                    ledger=ledger,
                    run_id=run_id,
                    shared_state=shared_state,
                )

        wrapper_tasks = [asyncio.create_task(_run_lane(lane)) for lane in ordered]
        deadline = timeout.cycle_timeout_s
        cycle_timed_out = False

        try:
            raw_results = await asyncio.wait_for(
                asyncio.gather(*wrapper_tasks, return_exceptions=True),
                timeout=deadline,
            )
        except asyncio.TimeoutError:
            cycle_timed_out = True
            # Wait briefly for wrappers to finish their cancellation cleanup.
            await asyncio.wait(wrapper_tasks, timeout=timeout.stuck_task_grace_s)
            raw_results = []
            for task in wrapper_tasks:
                if task.done() and not task.cancelled():
                    raw_results.append(task.result())
                else:
                    raw_results.append(None)

        # Normalize results and attach stuck/orphaned tasks.
        lane_results: list[MeshResult] = []
        for lane, raw in zip(ordered, raw_results):
            if isinstance(raw, MeshResult):
                lane_results.append(raw)
            elif isinstance(raw, BaseException):
                lane_results.append(
                    MeshResult(
                        lane_name=getattr(lane, "name", "unknown"),
                        state=LaneState.DEGRADED,
                        error=str(raw),
                    )
                )
            else:
                # Wrapper was cancelled/abandoned by cycle timeout.
                lane_results.append(
                    MeshResult(
                        lane_name=getattr(lane, "name", "unknown"),
                        state=LaneState.TIMED_OUT,
                        error="cycle timeout or abandonment",
                    )
                )

        # Collect any tasks that are still pending after the cycle timeout.
        for task in wrapper_tasks:
            if not task.done():
                run.stuck_tasks.append(task)
                task.add_done_callback(
                    lambda t: t.exception() if not t.cancelled() else None
                )

        run.finished_at = datetime.now(timezone.utc)
        if cycle_timed_out:
            run.state = LaneState.TIMED_OUT
        elif any(r.state != LaneState.COMPLETED for r in lane_results):
            run.state = LaneState.DEGRADED
        else:
            run.state = LaneState.COMPLETED
        run.lane_results = lane_results
        run.proof_refs = ledger.proof_refs.copy()
        return run

    async def _execute_lane(
        self,
        lane: Any,
        budget: MeshBudget,
        timeout: MeshTimeout,
        ledger: MeshProofLedger,
        run_id: str,
        shared_state: dict[str, Any],
    ) -> MeshResult:
        """Execute a single lane with per-lane timeout and stuck-task killer."""
        started_at = datetime.now(timezone.utc)
        lane_name = getattr(lane, "name", "unknown")

        if hasattr(lane, "state"):
            lane.state = LaneState.RUNNING

        heartbeat = MeshHeartbeat(
            lane_name=lane_name,
            state=LaneState.RUNNING,
            progress_pct=0.0,
        )
        ledger.record(
            event="lane_started",
            lane=lane_name,
            proof_ref=MeshProofRef(component="scheduler", verdict="lane_started"),
            heartbeat=heartbeat.model_dump(),
        )

        ctx = MeshContext(
            run_id=run_id,
            lane_name=lane_name,
            budget=budget,
            timeout=timeout,
            proof_ledger=ledger,
            shared_state=shared_state,
        )

        lane_task: asyncio.Task[Any] = asyncio.create_task(lane.execute(ctx))
        state = LaneState.READY
        error: str | None = None
        result_payload: Any = None
        lane_result_obj: MeshResult | None = None

        try:
            raw_result = await asyncio.wait_for(
                asyncio.shield(lane_task),
                timeout=timeout.per_lane_timeout_s,
            )
            if isinstance(raw_result, MeshResult):
                lane_result_obj = raw_result
                lane_result_obj.started_at = started_at
                state = lane_result_obj.state
            else:
                state = LaneState.COMPLETED
                result_payload = raw_result
        except asyncio.TimeoutError:
            error = f"per-lane timeout ({timeout.per_lane_timeout_s}s)"
            state = await self._cancel_or_quarantine(lane_task, timeout)
        except asyncio.CancelledError:
            # Cycle timeout or external cancellation.
            error = "cycle timeout or cancellation"
            state = await self._cancel_or_quarantine(lane_task, timeout)
        except Exception as exc:
            error = str(exc)
            state = LaneState.DEGRADED
            if not lane_task.done():
                lane_task.cancel()

        finished_at = datetime.now(timezone.utc)

        if hasattr(lane, "state"):
            lane.state = state

        proof = ledger.record(
            event=f"lane_{state.value.lower()}",
            lane=lane_name,
            proof_ref=MeshProofRef(
                component="scheduler",
                verdict=state.value,
                payload_hash="",
            ),
            duration_s=(finished_at - started_at).total_seconds(),
        )

        if lane_result_obj is not None:
            lane_result_obj.finished_at = finished_at
            lane_result_obj.events_recorded = ledger.count(lane=lane_name)
            return lane_result_obj

        return MeshResult(
            lane_name=lane_name,
            state=state,
            result=result_payload,
            error=error,
            started_at=started_at,
            finished_at=finished_at,
            proof_ref=proof,
            events_recorded=ledger.count(lane=lane_name),
        )

    async def _cancel_or_quarantine(
        self,
        lane_task: asyncio.Task[Any],
        timeout: MeshTimeout,
    ) -> LaneState:
        """Try to cancel ``lane_task``; quarantine it if it refuses to die.

        We use ``asyncio.wait(..., timeout=...)`` rather than ``wait_for`` so
        that a lane which swallows cancellation cannot block the scheduler.
        """
        lane_task.cancel()
        done, pending = await asyncio.wait(
            {lane_task},
            timeout=timeout.stuck_task_grace_s,
        )
        if lane_task in pending:
            # Stuck task: abandon it so the cycle can continue.
            lane_task.add_done_callback(
                lambda t: t.exception() if not t.cancelled() else None
            )
            return LaneState.QUARANTINED
        if lane_task.cancelled():
            return LaneState.TIMED_OUT
        try:
            lane_task.result()
        except Exception:
            return LaneState.DEGRADED
        return LaneState.TIMED_OUT
