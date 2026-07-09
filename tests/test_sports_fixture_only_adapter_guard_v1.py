from tests.v30_test_helpers import assert_v30_report_named


def test_sports_fixture_only_adapter_guard_v1_keeps_sports_terms_blocked() -> None:
    report = assert_v30_report_named(
        "sports_fixture_only_adapter_guard_v1_report.json",
        "sports_fixture_only_guard_status",
        "sports_source_mode",
    )

    assert report["sports_fixture_only_guard_status"] == "PASS"
    assert report["sports_source_mode"] == "FIXTURE_REPLAY_ONLY"
    assert report["sports_live_source_allowed"] is False
    assert report["wagering_activation_allowed"] is False
    assert report["fantasy_contest_entry_allowed"] is False
    assert report["questionable_odds_scraping"] is False
