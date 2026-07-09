from tests.v25_test_helpers import assert_current_test_report


def test_v25_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
