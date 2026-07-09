from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_no_trade_discipline_v2_records_abstention_without_artifacts() -> None:
    report = assert_current_test_report(__file__)
    assert report["no_trade_discipline_v2_status"] == "PASS_NO_TRADE_DISCIPLINE_RECORDED"
    assert report["no_trade_is_valid_intelligent_action"] is True
    assert report["shadow_orders_created"] is False
    assert report["dry_submit_packets_created"] is False
