from __future__ import annotations


def test_baseline_forecast_replay_ledgers_before_scoring() -> None:
    from predator_mesh.v17.baselines import BaselineForecastHarness

    report = BaselineForecastHarness().replay_report()

    assert report["ledgered_before_scoring"] is True
    assert report["sample_quality"] == "LOW_SAMPLE"
