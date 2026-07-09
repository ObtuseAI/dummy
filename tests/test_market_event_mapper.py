from tests.v22_test_helpers import assert_current_test_report


def test_v22_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["all_mappings_have_proof_refs"] is True
