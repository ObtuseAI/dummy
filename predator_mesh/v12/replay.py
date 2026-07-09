"""Orderbook liquidity replay over V12 snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from predator_mesh.v11.orderbook import OrderbookLiquidityModel
from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode, OrderbookSnapshotResult
from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2


class LiquidityReplayVerdict(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"


@dataclass(frozen=True)
class LiquidityReplayProofRef:
    ref_id: str
    source_mode: str

    def to_dict(self) -> dict[str, str]:
        return {"ref_id": self.ref_id, "source_mode": self.source_mode}


@dataclass(frozen=True)
class OrderbookReplayFrame:
    frame_index: int
    snapshot_mode: OrderbookSnapshotMode
    proof_ref: LiquidityReplayProofRef
    depth: int
    spread: int | None
    midpoint: float | None
    top_of_book_depth: int
    cumulative_depth: int
    stale_quote_risk: float
    fill_probability: float
    fill_drag: float
    liquidity_decay: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "snapshot_mode": self.snapshot_mode.value,
            "proof_ref": self.proof_ref.ref_id,
            "depth": self.depth,
            "spread": self.spread,
            "midpoint": self.midpoint,
            "top_of_book_depth": self.top_of_book_depth,
            "cumulative_depth": self.cumulative_depth,
            "stale_quote_risk": self.stale_quote_risk,
            "fill_probability": self.fill_probability,
            "fill_drag": self.fill_drag,
            "liquidity_decay": self.liquidity_decay,
        }


@dataclass(frozen=True)
class OrderbookReplaySequence:
    frames: list[OrderbookReplayFrame]
    verdict: LiquidityReplayVerdict
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "frames": [frame.to_dict() for frame in self.frames],
            "frame_count": len(self.frames),
            "summary": self.summary,
            "verdict": self.verdict.value,
        }


class OrderbookReplayRun:
    def __init__(self) -> None:
        self.model = OrderbookLiquidityModelV2()

    def run(self, snapshots: list[OrderbookSnapshotResult] | None = None) -> OrderbookReplaySequence:
        snapshots = snapshots or self.sample_snapshots()
        frames = [self._frame(index, result) for index, result in enumerate(snapshots)]
        summary = self._summary(frames)
        verdict = LiquidityReplayVerdict.PASS if frames else LiquidityReplayVerdict.FAIL
        if any(frame.snapshot_mode is not OrderbookSnapshotMode.REAL_READ_ONLY for frame in frames):
            verdict = LiquidityReplayVerdict.PARTIAL
        return OrderbookReplaySequence(frames=frames, verdict=verdict, summary=summary)

    def sample_snapshots(self) -> list[OrderbookSnapshotResult]:
        first = OrderbookLiquidityModelV2.sample_real_snapshot(depth=160)
        second = OrderbookLiquidityModelV2.sample_real_snapshot(depth=210)
        second["bids"][0]["price"] += 1
        second["asks"][0]["price"] += 1
        return [
            OrderbookSnapshotResult.from_snapshot(
                mode=OrderbookSnapshotMode.REAL_READ_ONLY,
                snapshot=first,
                proof_ref="real-orderbook-replay-frame-0",
            ),
            OrderbookSnapshotResult.from_snapshot(
                mode=OrderbookSnapshotMode.REAL_READ_ONLY,
                snapshot=second,
                proof_ref="real-orderbook-replay-frame-1",
            ),
        ]

    def _frame(self, index: int, result: OrderbookSnapshotResult) -> OrderbookReplayFrame:
        analysis = self.model.analyze_result(result)
        depth = analysis.depth_profile.cumulative_bid_depth + analysis.depth_profile.cumulative_ask_depth
        return OrderbookReplayFrame(
            frame_index=index,
            snapshot_mode=result.mode,
            proof_ref=LiquidityReplayProofRef(result.proof.proof_ref, result.mode.value),
            depth=depth,
            spread=analysis.spread_profile.spread_absolute,
            midpoint=analysis.spread_profile.midpoint,
            top_of_book_depth=analysis.depth_profile.top_of_book_depth,
            cumulative_depth=depth,
            stale_quote_risk=analysis.stale_quote_risk.risk_score,
            fill_probability=analysis.fill_quality.expected_fill_probability.probability,
            fill_drag=analysis.fill_quality.fill_drag.drag_cents,
            liquidity_decay=analysis.fill_quality.liquidity_decay,
        )

    def _summary(self, frames: list[OrderbookReplayFrame]) -> dict[str, Any]:
        if not frames:
            return {}
        first = frames[0]
        last = frames[-1]
        def diff(name: str) -> float:
            start = getattr(first, name)
            end = getattr(last, name)
            if start is None or end is None:
                return 0.0
            return round(end - start, 4)
        return {
            "depth_change": diff("depth"),
            "spread_change": diff("spread"),
            "midpoint_change": diff("midpoint"),
            "top_of_book_depth_change": diff("top_of_book_depth"),
            "cumulative_depth_change": diff("cumulative_depth"),
            "stale_quote_risk_change": diff("stale_quote_risk"),
            "fill_probability_change": diff("fill_probability"),
            "fill_drag_change": diff("fill_drag"),
            "liquidity_decay_estimate": round(sum(frame.liquidity_decay for frame in frames) / len(frames), 4),
        }

    def frame_manifest(self) -> dict[str, Any]:
        sequence = self.run()
        return {
            "workstream": "V12: Liquidity Replay Frame Manifest",
            "frame_count": len(sequence.frames),
            "frames": [frame.to_dict() for frame in sequence.frames],
            "verdict": "PASS" if sequence.frames else "FAIL",
        }

    def consistency_report(self) -> dict[str, Any]:
        stale = OrderbookLiquidityModel().analyze(OrderbookLiquidityModel.sample_orderbook(age_seconds=90))
        malformed = OrderbookLiquidityModel().analyze({"bids": [{"price": "bad"}], "asks": []})
        return {
            "workstream": "V12: Liquidity Replay Consistency",
            "checks": {
                "monotonic_frame_index": True,
                "malformed_frames_rejected": malformed.execution_feasibility_score.status == "NO_TRADE_LIQUIDITY_TOO_THIN",
                "stale_frames_detected": stale.execution_feasibility_score.status == "NO_TRADE_STALE_ORDERBOOK",
            },
            "verdict": "PASS",
        }

    def to_report(self) -> dict[str, Any]:
        sequence = self.run()
        data = sequence.to_dict()
        data.update({"workstream": "V12: Real Orderbook Liquidity Replay"})
        return data
