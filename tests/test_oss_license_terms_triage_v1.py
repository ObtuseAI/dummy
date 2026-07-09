from tests.v29_test_helpers import assert_v29_report_named


def test_oss_license_terms_triage_v1_blocks_unclear_commercial_scraping_and_execution_risks() -> None:
    report = assert_v29_report_named(
        "oss_license_terms_triage_v1_report.json",
        "license_terms_triage_status",
        "license_triage_verdict_counts",
        "unknown_license_dependency_candidate_count",
    )

    verdict_counts = report["license_triage_verdict_counts"]
    assert report["license_terms_triage_status"] == "PASS"
    assert report["not_legal_advice"] is True
    assert report["license_fields_are_signals_not_approval"] is True
    assert report["unknown_license_dependency_candidate_count"] == 0
    assert verdict_counts["TERMS_UNCLEAR_REFERENCE_ONLY"] > 0
    assert verdict_counts["BLOCKED_COMMERCIAL_OR_KEYED"] > 0
    assert verdict_counts["BLOCKED_SCRAPING_RISK"] > 0
    assert report["sports_terms_strict"] is True
    assert report["bloomberg_access_assumed"] is False
    assert report["mined_repo_cloned"] is False
    assert report["mined_repo_imported"] is False
    assert report["mined_repo_executed"] is False
