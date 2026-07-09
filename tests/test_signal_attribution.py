from __future__ import annotations


def test_signal_attribution_marks_helped_and_hurt_counts() -> None:
    from predator_mesh.v17.attribution import OutcomeAttributionEngine
    from tests.v17_test_helpers import fixture_forecasts_and_outcomes

    forecasts, outcomes = fixture_forecasts_and_outcomes()
    report = OutcomeAttributionEngine().signal_attribution_report(forecasts, outcomes)

    assert "helped_count" in report
    assert "hurt_count" in report
