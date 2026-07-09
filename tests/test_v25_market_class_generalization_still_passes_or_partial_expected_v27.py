from tests.v27_test_helpers import assert_current_test_report


def test_v25_market_class_generalization_still_passes_or_partial_expected_v27_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
