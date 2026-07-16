from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_sports_no_trade_gate_v2_blocks_unapproved_injury_and_market_sources() -> None:
    report = assert_v20_report("sports_no_trade_gate_v2_report.json", "no_trade_reasons")
    assert report["no_trade"] is True
