from __future__ import annotations

from v19_test_helpers import assert_domain_activation_report


def test_weather_readonly_source_activation_is_public_allowed_or_blocked() -> None:
    assert_domain_activation_report("weather")
