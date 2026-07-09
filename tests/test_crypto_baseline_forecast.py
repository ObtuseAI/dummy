from __future__ import annotations

from v18_test_helpers import assert_domain_baseline_forecast


def test_crypto_baseline_forecast_excludes_leverage_and_perp_trading() -> None:
    assert_domain_baseline_forecast("crypto")
