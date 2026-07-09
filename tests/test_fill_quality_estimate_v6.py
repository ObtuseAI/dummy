from __future__ import annotations

from tests.v16_test_helpers import pass_truth_verdict, real_snapshot


def test_fill_quality_estimate_v6_includes_fallback_reason_field() -> None:
    from predator_mesh.v16.liquidity_reports import LiquidityModelTerrainReporter

    report = LiquidityModelTerrainReporter(real_snapshot(), pass_truth_verdict()).fill_quality_estimate_report_v6()

    assert report["terrain_truth_verdict"] == "PASS_REAL_TERRAIN"
    assert report["fallback_reason"] == ""
