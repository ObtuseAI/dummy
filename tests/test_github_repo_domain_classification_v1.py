from tests.v28_test_helpers import assert_current_test_report


def test_github_repo_domain_classification_v1_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
