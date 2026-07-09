from tests.v28_test_helpers import assert_v28_report_named


def test_open_source_github_keyword_expansion_v1_covers_requested_domains() -> None:
    report = assert_v28_report_named(
        "open_source_github_gap_fill_accelerator_v1_report.json",
        "github_domain_counts",
        "github_search_keyword_coverage",
    )

    counts = report["github_domain_counts"]
    assert report["github_candidate_count"] >= 120
    assert counts["weather"] >= 15
    assert counts["sports"] >= 20
    assert counts["crypto"] >= 20
    assert counts["trading"] >= 20
    assert counts["bloomberg"] >= 10

    coverage = set(report["github_search_keyword_coverage"])
    assert {"basketball", "bloomberg", "bitcoin", "weather prediction", "crypto", "trading"} <= coverage
    assert report["github_mining_mode"] == "metadata_only_no_clone_no_import_no_execute"
    assert report["github_repo_code_executed"] is False
