from tests.v27_test_helpers import assert_current_test_report


def test_no_caps_config_modification_v27_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
