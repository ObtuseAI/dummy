from __future__ import annotations

from predator_mesh.v11.orderbook import OrderbookLiquidityModel


def test_fill_quality_estimate_tracks_drag_against_edge() -> None:
    report = OrderbookLiquidityModel().fill_quality_report()

    assert report["verdict"] == "PASS"
    assert report["estimate"]["expected_fill_probability"]["probability"] > 0
    assert report["estimate"]["fill_drag"]["edge_after_fill_drag"] > 0
    assert report["estimate"]["price_impact"]["impact_cents"] >= 0
