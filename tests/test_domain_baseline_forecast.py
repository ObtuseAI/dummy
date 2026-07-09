from __future__ import annotations


def test_domain_baseline_forecast_covers_original_domains() -> None:
    from predator_mesh.v17.baselines import BaselineForecastHarness

    report = BaselineForecastHarness().domain_forecast_report()

    assert set(report["domains"]) == {"sports", "weather", "crypto", "commodities", "finance"}
