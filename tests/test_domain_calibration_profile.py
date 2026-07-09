from __future__ import annotations


def test_domain_calibration_profile_separates_domains() -> None:
    from predator_mesh.v17.calibration import CalibrationEngine
    from tests.v17_test_helpers import fixture_forecasts_and_outcomes

    forecasts, outcomes = fixture_forecasts_and_outcomes()
    report = CalibrationEngine().domain_profile(forecasts, outcomes).to_report()

    assert set(report["domains"]) == {"sports", "weather"}
    assert report["profiles"]["sports"]["sample_quality"] == "LOW_SAMPLE"
