from __future__ import annotations


def test_readonly_outcome_observer_degrades_to_unresolved_without_fabricating() -> None:
    from predator_mesh.v17.observer import ReadOnlyOutcomeObserver

    report = ReadOnlyOutcomeObserver().observe().to_report()

    assert report["mode"] in {"UNRESOLVED_PENDING", "STATIC_FIXTURE_OUTCOME", "REAL_READ_ONLY_SETTLEMENT", "MANUAL_IMPORT_REQUIRED"}
    assert report["fabricated_outcome"] is False
