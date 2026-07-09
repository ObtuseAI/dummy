from tests.v28_test_helpers import assert_current_test_report


def test_crypto_open_source_public_adapter_plan_v1_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
