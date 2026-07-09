from __future__ import annotations

from predator_mesh.v14.no_trade_gates import FillDragNoTradeReport


def test_fill_drag_no_trade_report_blocks_excessive_fill_drag() -> None:
    report = FillDragNoTradeReport(fill_drag_bps=72.0, threshold_bps=30.0).to_report()

    assert report["trade_allowed"] is False
    assert report["fill_drag_bps"] > report["threshold_bps"]
    assert "FILL_DRAG_TOO_HIGH" in report["no_trade_reasons"]
    assert report["verdict"] == "PASS"
