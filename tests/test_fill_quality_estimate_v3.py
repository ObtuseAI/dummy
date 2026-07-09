from __future__ import annotations

from predator_mesh.v13.liquidity_terrain import OrderbookLiquidityTerrainV3
from tests.v13_test_helpers import real_snapshot_result


def test_fill_quality_estimate_v3_reports_real_snapshot_mode() -> None:
    report = OrderbookLiquidityTerrainV3(real_snapshot_result()).fill_quality_report()

    assert report["terrain_verdict"] == "PASS_REAL_TERRAIN"
    assert report["snapshot_mode"] == "REAL_READ_ONLY"
    assert report["verdict"] == "PASS"
