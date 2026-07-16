from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_oil_no_trade_gate_blocks_when_cl_and_brent_data_missing() -> None:
    report = assert_v20_report("oil_no_trade_gate_report_v1.json", "no_trade_reasons")
    assert report["no_trade"] is True
    assert "CL futures orderbook/trades" in report["no_trade_reasons"]
