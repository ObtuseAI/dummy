from __future__ import annotations

from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2


def test_fill_quality_estimate_v2_reports_real_terrain_mode_and_drag() -> None:
    report = OrderbookLiquidityModelV2().fill_quality_report_v2()

    assert report["workstream"] == "V12: Fill Quality Estimate V2"
    assert report["estimate"]["fill_drag"]["drag_cents"] >= 0
    assert report["snapshot_mode"] in {"REAL_READ_ONLY", "SAMPLE_STATIC_FALLBACK"}
    assert report["verdict"] == "PASS"
