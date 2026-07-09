from __future__ import annotations

from scripts.generate_v12_reports import generate_no_unauthorized_source_report_v12


def test_no_unauthorized_source_v12() -> None:
    report = generate_no_unauthorized_source_report_v12()

    assert report["verdict"] == "PASS"
    assert report["unauthorized_sources"] == []
    assert report["unbounded_scraping"] is False
