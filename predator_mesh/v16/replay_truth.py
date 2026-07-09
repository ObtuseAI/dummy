"""Real orderbook replay truth repair for V16."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from core.secret_guard import redact
from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode, OrderbookSnapshotResult
from predator_mesh.v12.replay import OrderbookReplayRun
from predator_mesh.v16.orderbook_snapshot import RealOrderbookSnapshotResultV2


@dataclass(frozen=True)
class RealOrderbookReplayFrameV2:
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return redact(self.data)


@dataclass(frozen=True)
class RealOrderbookReplaySelection:
    input_mode: str
    snapshot_source: str
    fallback_reason: str
    snapshot_result: OrderbookSnapshotResult


class RealOrderbookReplayInputSelector:
    def __init__(self, *, snapshot_result: RealOrderbookSnapshotResultV2 | OrderbookSnapshotResult) -> None:
        self.snapshot_result = snapshot_result

    def select(self) -> RealOrderbookReplaySelection:
        result = self._to_v12_result(self.snapshot_result)
        if result.mode is OrderbookSnapshotMode.REAL_READ_ONLY:
            return RealOrderbookReplaySelection(
                input_mode="REAL_SNAPSHOT_REPLAY",
                snapshot_source="config_bound_real_orderbook_snapshot",
                fallback_reason="",
                snapshot_result=result,
            )
        if result.mode is OrderbookSnapshotMode.REAL_READ_ONLY_DEGRADED and self._nonempty_real_snapshot(result):
            return RealOrderbookReplaySelection(
                input_mode="REAL_SNAPSHOT_REPLAY_WITH_WARNINGS",
                snapshot_source="config_bound_real_orderbook_snapshot",
                fallback_reason=result.proof.fallback_reason,
                snapshot_result=result,
            )
        return RealOrderbookReplaySelection(
            input_mode="SAMPLE_STATIC_FALLBACK_REPLAY",
            snapshot_source="sample_static_fallback",
            fallback_reason=result.proof.fallback_reason or "NO_VALID_REAL_SNAPSHOT",
            snapshot_result=result,
        )

    def _nonempty_real_snapshot(self, result: OrderbookSnapshotResult) -> bool:
        snapshot = result.snapshot if isinstance(result.snapshot, dict) else {}
        if snapshot.get("sample_orderbook_used") is True:
            return False
        bids = snapshot.get("bids") if isinstance(snapshot.get("bids"), list) else []
        asks = snapshot.get("asks") if isinstance(snapshot.get("asks"), list) else []
        return bool(bids or asks)

    def _to_v12_result(self, result: RealOrderbookSnapshotResultV2 | OrderbookSnapshotResult) -> OrderbookSnapshotResult:
        if isinstance(result, OrderbookSnapshotResult):
            return result
        return result.to_orderbook_snapshot_result()


class RealOrderbookReplayTruthRepair:
    def __init__(self, *, snapshot_result: RealOrderbookSnapshotResultV2 | OrderbookSnapshotResult) -> None:
        self.selection = RealOrderbookReplayInputSelector(snapshot_result=snapshot_result).select()

    def _frames(self) -> list[dict[str, Any]]:
        sequence = OrderbookReplayRun().run([self.selection.snapshot_result])
        frames = []
        for frame in sequence.frames:
            data = frame.to_dict()
            data["frame_hash"] = self._frame_hash(data)
            data["snapshot_source"] = self.selection.snapshot_source
            frames.append(RealOrderbookReplayFrameV2(data).to_dict())
        return frames

    def _frame_hash(self, frame: dict[str, Any]) -> str:
        payload = f"{frame.get('snapshot_mode')}|{frame.get('depth')}|{frame.get('spread')}|{frame.get('midpoint')}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def to_report(self) -> dict[str, Any]:
        frames = self._frames()
        hashes = [frame["frame_hash"] for frame in frames]
        return {
            "workstream": "V16: Real Orderbook Replay Truth Repair",
            "input_mode": self.selection.input_mode,
            "frame_count": len(frames),
            "snapshot_source": self.selection.snapshot_source,
            "snapshot_timestamp": self.selection.snapshot_result.snapshot.get("timestamp"),
            "stale_flag": any(frame.get("stale_quote_risk", 0) >= 0.5 for frame in frames),
            "duplicate_frame_count": len(hashes) - len(set(hashes)),
            "fallback_reason": self.selection.fallback_reason,
            "frames": frames,
            "secret_values_exposed": False,
            "verdict": "PASS" if self.selection.input_mode == "REAL_SNAPSHOT_REPLAY" else "PARTIAL",
        }

    def liquidity_replay_report_v5(self) -> dict[str, Any]:
        report = self.to_report()
        report.update({"workstream": "V16: Real Orderbook Liquidity Replay V5"})
        return report
