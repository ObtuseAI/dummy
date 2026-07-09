from __future__ import annotations

from v18_test_helpers import assert_domain_baseline_forecast


def test_commodities_baseline_forecast_uses_report_calendar_context() -> None:
    assert_domain_baseline_forecast("commodities")
