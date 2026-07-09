from tests.v27_test_helpers import assert_current_test_report


def test_sports_terms_resolution_workbench_v1_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
    assert report["odds_scraping"] is False
    assert report["undocumented_endpoint_activation"] is False
    assert report["sports_terms_ambiguity_converted_to_verdicts"] is True
    assert "FIXTURE_REPLAY_ONLY" in report["verdict_classes"]
