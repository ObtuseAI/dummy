from tests.v29_test_helpers import assert_v29_report_named


def test_sports_source_legality_resolver_v3_keeps_betting_fantasy_and_unsafe_sources_reference_only() -> None:
    report = assert_v29_report_named(
        "sports_source_legality_resolver_v3_report.json",
        "sports_legality_resolver_status",
        "sports_source_mode",
        "sports_candidate_count",
    )

    assert report["sports_legality_resolver_status"] == "PASS"
    assert report["sports_source_mode"] == "FIXTURE_REPLAY_ONLY"
    assert report["sports_candidate_count"] >= 55
    assert report["betting_candidate_count"] >= 18
    assert report["fantasy_candidate_count"] >= 18
    assert report["sports_live_source_allowed"] is False
    assert report["questionable_odds_scraping"] is False
    assert report["wagering_activation_allowed"] is False
    assert report["fantasy_contest_entry_allowed"] is False
    assert report["undocumented_sports_endpoint_activated"] is False
