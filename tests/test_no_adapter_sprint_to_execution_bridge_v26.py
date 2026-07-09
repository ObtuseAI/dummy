from tests.v26_test_helpers import assert_current_test_report


def test_no_adapter_sprint_to_execution_bridge_v26_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
