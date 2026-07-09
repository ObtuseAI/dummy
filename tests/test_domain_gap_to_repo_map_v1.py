from tests.v28_test_helpers import assert_current_test_report


def test_domain_gap_to_repo_map_v1_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
