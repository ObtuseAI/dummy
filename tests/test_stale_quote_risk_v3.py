from __future__ import annotations

from predator_mesh.v13.liquidity_terrain import OrderbookLiquidityTerrainV3


def test_stale_quote_risk_v3_keeps_fresh_and_stale_checks() -> None:
    report = OrderbookLiquidityTerrainV3().stale_quote_report()

    assert report["fresh"]["status"] == "FRESH"
    assert report["stale"]["status"] == "STALE"
    assert report["verdict"] == "PASS"
