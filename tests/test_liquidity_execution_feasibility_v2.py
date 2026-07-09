from __future__ import annotations

from tests.v16_test_helpers import pass_truth_verdict, real_snapshot


def test_liquidity_execution_feasibility_v2_keeps_timeout_bounds() -> None:
    from predator_mesh.v16.liquidity_reports import LiquidityModelTerrainReporter

    report = LiquidityModelTerrainReporter(real_snapshot(), pass_truth_verdict()).liquidity_execution_feasibility_report_v2()

    assert report["max_request_timeout_s"] <= 10
    assert report["max_adapter_timeout_s"] <= 45
    assert report["terrain_truth_verdict"] == "PASS_REAL_TERRAIN"
