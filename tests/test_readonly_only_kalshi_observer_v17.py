from __future__ import annotations


def test_readonly_only_kalshi_observer_v17_report_passes() -> None:
    from scripts.generate_v17_reports import generate_readonly_only_kalshi_observer_report_v17

    report = generate_readonly_only_kalshi_observer_report_v17()
    assert report["read_only_only"] is True
    assert report["verdict"] == "PASS"
