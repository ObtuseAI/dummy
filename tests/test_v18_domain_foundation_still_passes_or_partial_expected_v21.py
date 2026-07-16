from tests.v21_test_helpers import assert_current_test_report


def test_v21_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["v18_domain_foundation_status"] in {"PASS", "PARTIAL"}
