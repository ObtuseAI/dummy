from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_edge_no_trade_decision_has_no_live_execution() -> None:
    report = assert_v20_report("edge_no_trade_decision_report_v1.json", "decisions")
    assert report["no_trade_decision_count"] > 0
    assert report["live_execution_enabled"] is False

