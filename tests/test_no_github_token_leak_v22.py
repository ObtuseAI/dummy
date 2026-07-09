from tests.v22_test_helpers import assert_current_test_report


def test_v22_report_contract() -> None:
    assert_current_test_report(__file__)
