from tests.v28_test_helpers import assert_v28_report_named


def test_open_source_sports_wagering_keyword_expansion_v1_is_terms_gated() -> None:
    report = assert_v28_report_named(
        "open_source_github_gap_fill_accelerator_v1_report.json",
        "github_domain_counts",
        "github_search_keyword_coverage",
        "wagering_reference_only",
        "fantasy_reference_only",
    )

    counts = report["github_domain_counts"]
    assert report["github_candidate_count"] >= 240
    assert counts["sports"] >= 55
    assert counts["betting"] >= 18
    assert counts["fantasy"] >= 12

    coverage = set(report["github_search_keyword_coverage"])
    assert {
        "soccer",
        "football",
        "baseball",
        "betting",
        "wagering",
        "sportsbook",
        "gambling",
        "fantasy sports",
        "daily fantasy",
        "sports drafting",
    } <= coverage

    assert report["wagering_reference_only"] is True
    assert report["fantasy_reference_only"] is True
    assert report["betting_wagering_activation_allowed"] is False
    assert report["fantasy_contest_entry_allowed"] is False
    assert report["odds_scraping_allowed"] is False
    assert report["questionable_odds_scraping"] is False
    assert report["github_repo_code_executed"] is False
