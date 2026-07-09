from __future__ import annotations

from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode, OrderbookSnapshotResult
from predator_mesh.v12.replay import OrderbookReplayRun


def _snapshot(price_shift: int, depth: int) -> OrderbookSnapshotResult:
    return OrderbookSnapshotResult.from_snapshot(
        mode=OrderbookSnapshotMode.REAL_READ_ONLY,
        snapshot={
            "market_ticker": "KXDEMO",
            "contract_ticker": "KXDEMO-YES",
            "timestamp": "2026-07-02T00:00:00+00:00",
            "bids": [{"price": 48 + price_shift, "size": depth}],
            "asks": [{"price": 52 + price_shift, "size": depth + 20}],
            "requested_size": 5,
            "expected_edge_cents": 8.0,
        },
        proof_ref="snapshot-proof",
    )


def test_real_orderbook_liquidity_replay_computes_frame_changes() -> None:
    sequence = OrderbookReplayRun().run([_snapshot(0, 80), _snapshot(1, 110)])

    assert sequence.verdict.value == "PASS"
    assert len(sequence.frames) == 2
    assert sequence.summary["midpoint_change"] == 1.0
    assert sequence.summary["top_of_book_depth_change"] == 60
    assert sequence.summary["fill_probability_change"] >= 0
    assert sequence.summary["liquidity_decay_estimate"] >= 0
