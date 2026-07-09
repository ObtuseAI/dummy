from tests.v22_test_helpers import assert_current_test_report


def test_v22_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["context_evidence_claimed_edge"] is False
    assert report["fixture_evidence_claimed_edge"] is False
