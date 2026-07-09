from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_crypto_no_trade_gate_v2_blocks_terms_and_adapter_gaps() -> None:
    report = assert_v20_report("crypto_no_trade_gate_v2_report.json", "no_trade_reasons")
    assert report["no_trade"] is True
    assert report["live_execution_enabled"] is False

