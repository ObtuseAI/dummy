from __future__ import annotations

from predator_mesh.v13.liquidity_terrain import OrderbookLiquidityTerrainV3
from tests.v13_test_helpers import real_snapshot_result


def test_orderbook_liquidity_model_v3_distinguishes_real_terrain_pass() -> None:
    report = OrderbookLiquidityTerrainV3(real_snapshot_result()).orderbook_model_report()

    assert report["terrain_verdict"] == "PASS_REAL_TERRAIN"
    assert report["sample_orderbook_used"] is False
    assert report["verdict"] == "PASS"
