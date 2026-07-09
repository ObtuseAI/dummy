from tests.v26_test_helpers import assert_current_test_report


def test_keyless_public_adapter_capability_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
