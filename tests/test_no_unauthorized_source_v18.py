from __future__ import annotations


def test_no_unauthorized_source_v18_report_passes() -> None:
    from scripts.generate_v18_reports import generate_no_unauthorized_source_report_v18

    report = generate_no_unauthorized_source_report_v18()
    assert report["unauthorized_sources"] == []
    assert report["unbounded_scraping_introduced"] is False
