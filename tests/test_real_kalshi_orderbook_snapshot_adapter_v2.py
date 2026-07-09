from __future__ import annotations

import pytest

from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode
from predator_mesh.v13.orderbook_snapshot_v2 import RealKalshiOrderbookSnapshotAdapterV2
from tests.v13_test_helpers import FakeRealKalshiReadOnlyClient, ready_bridge


@pytest.mark.asyncio
async def test_real_kalshi_orderbook_snapshot_adapter_v2_captures_real_read_only_book(tmp_path) -> None:
    client = FakeRealKalshiReadOnlyClient()
    closure = await RealKalshiOrderbookSnapshotAdapterV2(
        credential_bridge=ready_bridge(tmp_path),
        read_only_client_factory=lambda: client,
    ).capture()

    assert closure.outcome == "REAL_READ_ONLY"
    assert closure.snapshot_result.mode is OrderbookSnapshotMode.REAL_READ_ONLY
    assert closure.snapshot_result.proof.order_endpoints_called == []
    assert closure.snapshot_result.proof.cancel_endpoints_called == []
