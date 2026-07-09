from __future__ import annotations


def test_no_questionable_odds_scraping_v19_report_passes() -> None:
    from scripts.generate_v19_reports import generate_no_questionable_odds_scraping_report_v19

    report = generate_no_questionable_odds_scraping_report_v19()
    assert report["questionable_odds_scraping_added"] is False
    assert report["verdict"] == "PASS"
