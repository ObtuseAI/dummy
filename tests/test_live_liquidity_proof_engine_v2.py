from __future__ import annotations

from predator_mesh.v12.liquidity_v2 import LiveLiquidityProofEngineV2
from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode, OrderbookSnapshotResult
from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2


def test_live_liquidity_proof_engine_v2_consumes_real_orderbook_terrain() -> None:
    result = OrderbookSnapshotResult.from_snapshot(
        mode=OrderbookSnapshotMode.REAL_READ_ONLY,
        snapshot=OrderbookLiquidityModelV2.sample_real_snapshot(),
        proof_ref="real-orderbook-proof",
    )

    packet = LiveLiquidityProofEngineV2().evaluate_snapshot(result)

    assert packet.snapshot_mode == OrderbookSnapshotMode.REAL_READ_ONLY
    assert packet.live_submit_required is False
    assert packet.firewall_rehearsal_status == "BLOCKED_LIVE_SUBMIT_DISABLED"
    assert packet.proof_refs["orderbook_snapshot"] == "real-orderbook-proof"
