"""V12 real orderbook terrain proof components.

V12 consumes Kalshi READ_ONLY orderbook terrain when available and degrades
explicitly to deterministic fallback snapshots when live read-only data is not
available. It never submits or cancels real orders.
"""

from predator_mesh.v12.orderbook_snapshot import (
    OrderbookSnapshotMode,
    OrderbookSnapshotRequest,
    OrderbookSnapshotResult,
    RealKalshiOrderbookSnapshotAdapter,
)
from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2
from predator_mesh.v12.liquidity_v2 import LiveLiquidityProofEngineV2

__all__ = [
    "LiveLiquidityProofEngineV2",
    "OrderbookLiquidityModelV2",
    "OrderbookSnapshotMode",
    "OrderbookSnapshotRequest",
    "OrderbookSnapshotResult",
    "RealKalshiOrderbookSnapshotAdapter",
]
