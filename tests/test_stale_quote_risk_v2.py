from __future__ import annotations

from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2


def test_stale_quote_risk_v2_keeps_stale_frame_detection() -> None:
    report = OrderbookLiquidityModelV2().stale_quote_report_v2()

    assert report["fresh"]["status"] == "FRESH"
    assert report["stale"]["status"] == "STALE"
    assert report["verdict"] == "PASS"
