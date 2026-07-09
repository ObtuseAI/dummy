from __future__ import annotations


def test_outcome_observer_activation_v2_is_readonly_and_does_not_fabricate() -> None:
    from predator_mesh.v19.outcome_observer import OutcomeObserverActivationV2

    report = OutcomeObserverActivationV2().to_report()
    assert report["verdict"] in {"PASS", "PARTIAL"}
    assert report["read_only_only"] is True
    assert report["fabricated_outcomes"] is False
