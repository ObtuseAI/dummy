from tests.v21_test_helpers import assert_current_test_report


def test_v21_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["v19_activation_architecture_status"] in {"PASS", "PARTIAL"}
