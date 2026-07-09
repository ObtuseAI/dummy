from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_forecast_quality_ledger_v1_stays_separate_from_execution() -> None:
    report = assert_current_test_report(__file__)
    assert report["forecast_quality_ledger_status"] == "PASS"
    assert report["forecast_quality_to_execution_bridge_present"] is False
    assert report["trading_signal_exported"] is False
    assert report["pnl_claim_made"] is False
