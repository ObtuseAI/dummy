from tests.v27_test_helpers import assert_current_test_report


def test_domain_market_class_scoreboard_v12_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
