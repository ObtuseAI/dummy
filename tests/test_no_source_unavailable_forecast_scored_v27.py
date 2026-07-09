from tests.v27_test_helpers import assert_current_test_report


def test_no_source_unavailable_forecast_scored_v27_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
