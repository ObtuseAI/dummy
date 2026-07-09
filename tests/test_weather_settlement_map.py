from __future__ import annotations

from v18_test_helpers import assert_domain_settlement_map


def test_weather_settlement_map_requires_station_and_time_window() -> None:
    assert_domain_settlement_map("weather")
