from __future__ import annotations

from archive.report_scripts.generate_v12_reports import generate_kalshi_read_only_still_passes_report_v12


def test_kalshi_read_only_still_passes_v12() -> None:
    report = generate_kalshi_read_only_still_passes_report_v12()

    assert report["verdict"] == "PASS"
    assert report["order_creating_endpoints_called"] == []
