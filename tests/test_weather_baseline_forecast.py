from __future__ import annotations

from v18_test_helpers import assert_domain_baseline_forecast


def test_weather_baseline_forecast_uses_consensus_and_persistence_lanes() -> None:
    assert_domain_baseline_forecast("weather")
