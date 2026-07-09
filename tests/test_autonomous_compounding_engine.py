from __future__ import annotations


def test_autonomous_compounding_engine_generates_non_executing_proposals() -> None:
    from predator_mesh.v19.compounding import AutonomousCompoundingEngine

    report = AutonomousCompoundingEngine().to_report()
    assert report["verdict"] == "PASS"
    assert report["proposals_mutate_production"] is False
    assert report["live_trading_proposals"] == []
