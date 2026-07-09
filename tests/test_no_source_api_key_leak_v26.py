from tests.v26_test_helpers import assert_current_test_report


def test_no_source_api_key_leak_v26_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
