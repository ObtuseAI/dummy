from tests.v27_test_helpers import assert_current_test_report


def test_settlement_rule_library_v1_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
    assert report["settlement_rule_count"] >= 12
    assert "KALSHI_MARKET_MAPPED" in report["rule_families"]
    assert report["no_score_without_settlement_rule"] is True
    assert report["private_or_unapproved_data_required"] is False
