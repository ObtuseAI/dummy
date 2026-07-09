from __future__ import annotations


def test_calibration_drift_low_sample_is_explicit() -> None:
    from predator_mesh.v17.calibration import CalibrationEngine
    from tests.v17_test_helpers import fixture_forecasts_and_outcomes

    forecasts, outcomes = fixture_forecasts_and_outcomes()
    report = CalibrationEngine().drift_report(forecasts, outcomes)

    assert report["drift_state"] == "LOW_SAMPLE"
    assert report["statistical_significance_claimed"] is False
