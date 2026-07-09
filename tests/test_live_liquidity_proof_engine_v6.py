from __future__ import annotations

from tests.v16_test_helpers import pass_truth_verdict, real_snapshot


def test_live_liquidity_proof_engine_v6_uses_real_terrain_truth() -> None:
    from predator_mesh.v16.liquidity_reports import LiquidityModelTerrainReporter

    report = LiquidityModelTerrainReporter(real_snapshot(), pass_truth_verdict()).live_liquidity_proof_engine_report_v6()

    assert report["terrain_mode"] == "REAL_READ_ONLY"
    assert report["terrain_truth_verdict"] == "PASS_REAL_TERRAIN"
