from __future__ import annotations

from predator_mesh.v13.liquidity_terrain import OrderbookLiquidityTerrainV3
from tests.v13_test_helpers import real_snapshot_result


def test_live_liquidity_proof_engine_v3_has_no_submit_or_cancel_calls() -> None:
    report = OrderbookLiquidityTerrainV3(real_snapshot_result()).live_liquidity_report()

    assert report["terrain_verdict"] == "PASS_REAL_TERRAIN"
    assert report["real_submit_calls"] == 0
    assert report["real_cancel_calls"] == 0
    assert report["live_submit_required"] is False
