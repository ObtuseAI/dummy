from tests.v27_test_helpers import assert_current_test_report


def test_weather_live_settlement_resolver_v3_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
