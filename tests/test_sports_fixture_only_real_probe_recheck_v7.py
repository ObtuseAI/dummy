from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_sports_fixture_only_real_probe_recheck_v7() -> None:
    report = assert_current_test_report(__file__)
    assert report["sports_mode"] == "FIXTURE_REPLAY_ONLY"
    assert report["no_odds_scraping"] is True
    assert report["no_wagering"] is True
    assert report["no_undocumented_endpoints"] is True
    assert report["execution_bridge_present"] is False
