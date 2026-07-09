from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_no_trade_discipline_v3_scores_abstention_quality_only() -> None:
    report = assert_current_test_report(__file__)
    assert report["no_trade_discipline_v3_status"] == "PASS_NO_TRADE_DISCIPLINE_RECORDED"
    assert "calibration tier too low" in report["abstention_reasons"]
    assert report["shadow_orders_created"] is False
    assert report["dry_submit_packets_created"] is False
