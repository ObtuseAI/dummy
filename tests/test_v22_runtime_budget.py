from tests.v22_test_helpers import assert_current_test_report


def test_v22_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["recursive_pytest_allowed"] is False
    assert report["unit_tests_use_fixtures"] is True
