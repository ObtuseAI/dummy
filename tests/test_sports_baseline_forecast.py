from __future__ import annotations

from v18_test_helpers import assert_domain_baseline_forecast


def test_sports_baseline_forecast_is_transparent_and_non_ml() -> None:
    assert_domain_baseline_forecast("sports")
