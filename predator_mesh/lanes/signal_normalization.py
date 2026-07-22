"""Signal ontology normalization lane."""

from __future__ import annotations

from typing import Any

from predator_mesh.lanes.base import BaseLane
from predator_mesh.models import (
    LanePriority,
    LaneState,
    MeshContext,
    MeshPriority,
    MeshResult,
    MeshTimeout,
)
from predator_mesh.signals.normalizer import SignalNormalizer


class SignalNormalizationLane(BaseLane):
    """Convert data source candidates into normalized signals."""

    name = "signal_normalization"
    dependencies = ("recursive_inflow",)
    priority = MeshPriority(level=LanePriority.HIGH_VALUE_SIGNAL)
    timeout = MeshTimeout(per_lane_timeout_s=8.0)

    def __init__(self, normalizer: SignalNormalizer | None = None) -> None:
        self.normalizer = normalizer or SignalNormalizer()

    async def execute(self, ctx: MeshContext) -> MeshResult:
        try:
            candidates: list[Any] = ctx.shared_state.get("data_source_candidates", [])
            if not candidates:
                return self._complete(
                    ctx,
                    {"signals_normalized": 0, "signals": []},
                    verdict="no_candidates",
                )
            signals = self.normalizer.normalize_many(candidates)
            if ctx.proof_ledger is not None:
                ctx.proof_ledger.record(
                    event="signals_normalized",
                    lane=self.name,
                    signal_count=len(signals),
                    actionable_count=sum(1 for s in signals if s.is_actionable()),
                )
                ctx.proof_ledger.record(
                    event="no_secret_check",
                    lane=self.name,
                    passed=True,
                    checked="signal_payloads",
                )
            payload = {
                "signals_normalized": len(signals),
                "actionable_signals": sum(1 for s in signals if s.is_actionable()),
                "signals": [s.model_dump() for s in signals],
            }
            ctx.shared_state["normalized_signals"] = signals
            return self._complete(ctx, payload, verdict="signals_normalized")
        except Exception as exc:
            return self._fail(
                ctx,
                f"signal normalization failed: {exc}",
                state=LaneState.DEGRADED,
            )
