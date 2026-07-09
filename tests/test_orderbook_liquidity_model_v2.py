from __future__ import annotations

from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode, OrderbookSnapshotResult
from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2


def test_orderbook_liquidity_model_v2_uses_real_mode_when_snapshot_is_real() -> None:
    result = OrderbookSnapshotResult.from_snapshot(
        mode=OrderbookSnapshotMode.REAL_READ_ONLY,
        snapshot=OrderbookLiquidityModelV2.sample_real_snapshot(),
        proof_ref="real-orderbook-proof",
    )

    report = OrderbookLiquidityModelV2().to_report(result)

    assert report["snapshot_mode"] == "REAL_READ_ONLY"
    assert report["sample_orderbook_used"] is False
    assert report["analysis"]["execution_feasibility_score"]["status"] in {"FEASIBLE", "NO_TRADE_SPREAD_TOO_WIDE"}
    assert report["verdict"] == "PASS"
