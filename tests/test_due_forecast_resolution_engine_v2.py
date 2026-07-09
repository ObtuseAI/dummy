from tests.v27_test_helpers import assert_current_test_report


def test_due_forecast_resolution_engine_v2_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
    assert report["reads_live_forecasts_from_versions"] == ["V22", "V23", "V24", "V25", "V26"]
    assert report["unresolved_forecasts_scored"] is False
    assert report["outcome_fabricated"] is False
    assert report["observer_to_execution_bridge"] is False
