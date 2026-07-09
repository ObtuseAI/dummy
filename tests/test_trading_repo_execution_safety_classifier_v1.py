from tests.v28_test_helpers import assert_current_test_report


def test_trading_repo_execution_safety_classifier_v1_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
