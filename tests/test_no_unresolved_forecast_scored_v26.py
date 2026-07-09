from tests.v26_test_helpers import assert_current_test_report


def test_no_unresolved_forecast_scored_v26_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
    assert report["unresolved_forecasts_scored"] is False
    assert report["verdict"] == "PASS"
