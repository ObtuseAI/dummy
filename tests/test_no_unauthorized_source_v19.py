from __future__ import annotations


def test_no_unauthorized_source_v19_report_passes() -> None:
    from archive.report_scripts.generate_v19_reports import generate_no_unauthorized_source_report_v19

    report = generate_no_unauthorized_source_report_v19()
    assert report["unauthorized_sources"] == []
    assert report["verdict"] == "PASS"
