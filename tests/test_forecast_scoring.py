from __future__ import annotations


def test_forecast_scoring_report_includes_log_loss_and_unresolved_rate() -> None:
    from predator_mesh.v17.calibration import CalibrationEngine
    from tests.v17_test_helpers import fixture_forecasts_and_outcomes

    forecasts, outcomes = fixture_forecasts_and_outcomes()
    report = CalibrationEngine().forecast_scoring_report(forecasts, outcomes)

    assert "log_loss" in report
    assert report["unresolved_outcome_rate"] == 0
