from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_nasdaq_no_trade_gate_blocks_when_nq_data_missing() -> None:
    report = assert_v20_report("nasdaq_no_trade_gate_report_v1.json", "no_trade_reasons")
    assert report["no_trade"] is True
    assert "NQ futures orderbook/trades" in report["no_trade_reasons"]

