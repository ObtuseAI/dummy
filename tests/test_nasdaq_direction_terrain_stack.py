from __future__ import annotations


def test_nasdaq_terrain_marks_exchange_native_blockers_before_forecast() -> None:
    from predator_mesh.v20.terrain import NasdaqDirectionTerrainStack

    stack = NasdaqDirectionTerrainStack()
    report = stack.to_report()
    blocker = stack.source_blocker_report()
    no_trade = stack.no_trade_gate_report()

    assert report["verdict"] == "PARTIAL"
    assert "NQ futures orderbook/trades" in report["required_source_needs"]
    assert blocker["exchange_native_missing"] is True
    assert no_trade["no_trade"] is True
    assert no_trade["live_execution_enabled"] is False
