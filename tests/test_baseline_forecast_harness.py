from __future__ import annotations


def test_baseline_forecast_harness_generates_transparent_deterministic_baselines() -> None:
    from predator_mesh.v17.baselines import BaselineForecastHarness

    report = BaselineForecastHarness().to_report()

    assert "market_implied_baseline" in report["strategies"]
    assert report["heavy_ml_used"] is False
