from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_edge_confidence_policy_blocks_heavy_ml_and_exchange_missing_forecasts() -> None:
    report = assert_v20_report("edge_confidence_policy_report_v1.json", "exchange_native_missing_forces_no_trade_for")
    assert report["heavy_ml_allowed"] is False
    assert {"nasdaq", "oil"} <= set(report["exchange_native_missing_forces_no_trade_for"])

