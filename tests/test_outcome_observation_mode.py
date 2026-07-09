from __future__ import annotations


def test_outcome_observation_mode_lists_real_degraded_fixture_pending_and_manual() -> None:
    from predator_mesh.v17.observer import ReadOnlyOutcomeObserver

    report = ReadOnlyOutcomeObserver.mode_report()

    assert {"REAL_READ_ONLY_SETTLEMENT", "REAL_READ_ONLY_DEGRADED", "STATIC_FIXTURE_OUTCOME", "UNRESOLVED_PENDING", "MANUAL_IMPORT_REQUIRED"}.issubset(report["modes"])
