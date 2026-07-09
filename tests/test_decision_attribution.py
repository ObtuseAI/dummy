from __future__ import annotations


def test_decision_attribution_remains_unresolved_without_outcome() -> None:
    from predator_mesh.v17.attribution import OutcomeAttributionEngine

    report = OutcomeAttributionEngine().decision_attribution_report([], [])

    assert report["unresolved_count"] >= 0
    assert report["verdict"] == "PASS"
