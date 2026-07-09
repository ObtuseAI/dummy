from __future__ import annotations

from v18_test_helpers import assert_domain_baseline_forecast


def test_finance_baseline_forecast_uses_prior_and_consensus_placeholders() -> None:
    assert_domain_baseline_forecast("finance")
