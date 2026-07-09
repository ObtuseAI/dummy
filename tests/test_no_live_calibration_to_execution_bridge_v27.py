from tests.v27_test_helpers import assert_current_test_report


def test_no_live_calibration_to_execution_bridge_v27_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
