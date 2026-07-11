from __future__ import annotations


def test_readonly_only_kalshi_observer_v18_report_passes() -> None:
    from archive.report_scripts.generate_v18_reports import generate_readonly_only_kalshi_observer_report_v18

    report = generate_readonly_only_kalshi_observer_report_v18()
    assert report["read_only_only"] is True
    assert report["write_endpoints_called"] == []
