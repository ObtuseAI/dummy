from __future__ import annotations

from tests.v16_test_helpers import pass_truth_verdict, real_snapshot


def test_orderbook_liquidity_model_v6_includes_terrain_truth() -> None:
    from predator_mesh.v16.liquidity_reports import LiquidityModelTerrainReporter

    report = LiquidityModelTerrainReporter(real_snapshot(), pass_truth_verdict()).orderbook_liquidity_model_report_v6()

    assert report["terrain_mode"] == "REAL_READ_ONLY"
    assert report["terrain_truth_verdict"] == "PASS_REAL_TERRAIN"
    assert report["source_snapshot_proof_ref"]
