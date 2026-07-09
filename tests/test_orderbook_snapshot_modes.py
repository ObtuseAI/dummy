from __future__ import annotations

import pytest

from predator_mesh.v12.orderbook_snapshot import (
    OrderbookSnapshotMode,
    OrderbookSnapshotRequest,
    RealKalshiOrderbookSnapshotAdapter,
)
from scripts.generate_v12_reports import generate_orderbook_snapshot_mode_report_v1


class FailingReadOnlyClient:
    async def get_orderbook(self, ticker: str) -> dict:
        raise RuntimeError("read-only orderbook unavailable")


@pytest.mark.asyncio
async def test_orderbook_snapshot_degrades_to_sample_static_fallback_without_claiming_real_proof() -> None:
    adapter = RealKalshiOrderbookSnapshotAdapter(read_only_client=FailingReadOnlyClient())

    result = await adapter.capture(OrderbookSnapshotRequest(contract_ticker="KXDEMO-YES"))

    assert result.mode is OrderbookSnapshotMode.SAMPLE_STATIC_FALLBACK
    assert result.proof.real_read_only_succeeded is False
    assert result.proof.fallback_reason == "read-only orderbook unavailable"
    assert result.snapshot["sample_orderbook_used"] is True


def test_orderbook_snapshot_mode_report_counts_real_and_fallback_modes() -> None:
    report = generate_orderbook_snapshot_mode_report_v1(
        modes=[
            OrderbookSnapshotMode.REAL_READ_ONLY,
            OrderbookSnapshotMode.SAMPLE_STATIC_FALLBACK,
        ]
    )

    assert report["mode_counts"]["REAL_READ_ONLY"] == 1
    assert report["mode_counts"]["SAMPLE_STATIC_FALLBACK"] == 1
    assert report["verdict"] == "PARTIAL"
