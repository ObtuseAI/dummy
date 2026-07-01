"""Abstract base class for all mesh lanes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from predator_mesh.models import (
    LanePriority,
    LaneState,
    MeshContext,
    MeshHeartbeat,
    MeshPriority,
    MeshProofRef,
    MeshResult,
    MeshTimeout,
)


class BaseLane(ABC):
    """A single mesh lane.

    Subclasses define ``name``, ``priority`` and ``timeout`` defaults and
    implement ``execute(ctx)``.
    """

    name: str = "base"
    priority: MeshPriority = MeshPriority()
    timeout: MeshTimeout = MeshTimeout()
    state: LaneState = LaneState.READY

    @abstractmethod
    async def execute(self, ctx: MeshContext) -> MeshResult:
        """Run the lane and return a typed result."""
        raise NotImplementedError

    def _heartbeat(self, ctx: MeshContext, progress_pct: float) -> MeshHeartbeat:
        heartbeat = MeshHeartbeat(
            lane_name=self.name,
            state=LaneState.RUNNING,
            progress_pct=progress_pct,
        )
        if ctx.proof_ledger is not None:
            ctx.proof_ledger.record(
                event="lane_heartbeat",
                lane=self.name,
                proof_ref=MeshProofRef(
                    component=self.name,
                    verdict="heartbeat",
                    payload_hash="",
                ),
                progress_pct=progress_pct,
            )
        return heartbeat

    def _complete(
        self,
        ctx: MeshContext,
        payload: Any,
        verdict: str = "completed",
    ) -> MeshResult:
        now = datetime.now(timezone.utc)
        proof = MeshProofRef(component=self.name, verdict=verdict)
        if ctx.proof_ledger is not None:
            ctx.proof_ledger.record(
                event="lane_completed",
                lane=self.name,
                proof_ref=proof,
            )
        return MeshResult(
            lane_name=self.name,
            state=LaneState.COMPLETED,
            result=payload,
            started_at=now,
            finished_at=now,
            proof_ref=proof,
        )

    def _fail(
        self,
        ctx: MeshContext,
        error: str,
        state: LaneState = LaneState.DEGRADED,
    ) -> MeshResult:
        now = datetime.now(timezone.utc)
        proof = MeshProofRef(component=self.name, verdict=state.value)
        if ctx.proof_ledger is not None:
            ctx.proof_ledger.record(
                event=f"lane_{state.value.lower()}",
                lane=self.name,
                proof_ref=proof,
                error=error,
            )
        return MeshResult(
            lane_name=self.name,
            state=state,
            error=error,
            started_at=now,
            finished_at=now,
            proof_ref=proof,
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} state={self.state}>"
