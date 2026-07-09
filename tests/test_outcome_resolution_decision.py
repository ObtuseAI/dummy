from __future__ import annotations


def test_outcome_resolution_decision_preserves_unresolved_without_fabrication() -> None:
    from predator_mesh.v19.outcome_observer import OutcomeObserverActivationV2

    report = OutcomeObserverActivationV2().resolution_decision_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["fabricated_outcomes"] is False
    assert report["unresolved_preserved"] is True
