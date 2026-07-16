from __future__ import annotations

from tests.v20_test_helpers import assert_security_report


def test_no_questionable_odds_scraping_v20_report_passes() -> None:
    report = assert_security_report("generate_no_questionable_odds_scraping_report_v20")
    assert report["questionable_odds_scraping_added"] is False
