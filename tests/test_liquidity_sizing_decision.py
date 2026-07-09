from __future__ import annotations

from predator_mesh.v11.aggression import LiquidityAggressionGovernor


def test_liquidity_sizing_decision_reduces_size_under_drag() -> None:
    report = LiquidityAggressionGovernor().sizing_report(fill_drag=0.45)

    assert report["verdict"] == "PASS"
    assert report["decision"]["decision"] == "REDUCE_SIZE"
    assert report["decision"]["size"] < report["decision"]["requested_size"]
