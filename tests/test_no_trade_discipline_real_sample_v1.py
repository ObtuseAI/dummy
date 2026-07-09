from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report


def test_no_trade_discipline_real_sample_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["no_trade_discipline_status"] == "PASS_NO_TRADE_DISCIPLINE_RECORDED"
    assert report["no_trade_is_valid_intelligent_action"] is True
    assert report["shadow_orders_created"] is False
    assert report["dry_submit_packets_created"] is False
    assert report["no_trade_discipline_to_execution_bridge_present"] is False
