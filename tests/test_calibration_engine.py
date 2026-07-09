from __future__ import annotations


def test_calibration_engine_scores_fixture_forecasts_with_brier_and_low_sample_label() -> None:
    from predator_mesh.v17.calibration import CalibrationEngine
    from tests.v17_test_helpers import fixture_forecasts_and_outcomes

    forecasts, outcomes = fixture_forecasts_and_outcomes()
    result = CalibrationEngine().score(forecasts, outcomes)

    assert result.sample_size == 2
    assert 0 <= result.brier_score <= 1
    assert result.sample_quality == "LOW_SAMPLE"
