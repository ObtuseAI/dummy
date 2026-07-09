from __future__ import annotations

from v18_test_helpers import assert_domain_research_foundation


def test_weather_research_foundation_tracks_location_window_and_uncertainty() -> None:
    assert_domain_research_foundation("weather")
