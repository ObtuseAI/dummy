from __future__ import annotations

from scripts.generate_v11_reports import generate_no_unauthorized_source_report_v11


def test_no_unauthorized_source_v11() -> None:
    report = generate_no_unauthorized_source_report_v11()
    assert report["verdict"] == "PASS"
    assert report["unauthorized_sources"] == []
    assert report["unbounded_scraping"] is False
