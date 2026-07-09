from __future__ import annotations

from datetime import datetime, timezone

import pytest

from predator_mesh.v12.orderbook_snapshot import (
    OrderbookSnapshotMode,
    OrderbookSnapshotRequest,
    RealKalshiOrderbookSnapshotAdapter,
)


class FakeReadOnlyOrderbookClient:
    def __init__(self) -> None:
        self.called: list[str] = []

    async def get_orderbook(self, ticker: str) -> dict:
        self.called.append(f"GET /markets/{ticker}/orderbook")
        return {
            "market_ticker": ticker,
            "contract_ticker": ticker,
            "bids": [{"price": 47, "size": 80}, {"price": 46, "size": 40}],
            "asks": [{"price": 51, "size": 90}, {"price": 52, "size": 30}],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def create_order(self, order: dict) -> None:
        raise AssertionError("V12 orderbook adapter must not submit orders")

    async def cancel_order(self, order_id: str) -> None:
        raise AssertionError("V12 orderbook adapter must not cancel orders")


@pytest.mark.asyncio
async def test_real_kalshi_orderbook_snapshot_adapter_uses_read_only_get_only_path() -> None:
    client = FakeReadOnlyOrderbookClient()
    adapter = RealKalshiOrderbookSnapshotAdapter(read_only_client=client)

    result = await adapter.capture(OrderbookSnapshotRequest(contract_ticker="KXDEMO-YES"))

    assert result.mode is OrderbookSnapshotMode.REAL_READ_ONLY
    assert result.proof.read_only is True
    assert result.proof.request_timeout_s <= 10
    assert result.proof.adapter_timeout_s <= 45
    assert result.proof.order_endpoints_called == []
    assert result.proof.cancel_endpoints_called == []
    assert client.called == ["GET /markets/KXDEMO-YES/orderbook"]
    assert result.snapshot["bids"][0]["price"] == 47
