from __future__ import annotations

from scripts.generate_v11_reports import generate_kalshi_read_only_still_passes_report_v11


def test_kalshi_read_only_still_passes_v11() -> None:
    report = generate_kalshi_read_only_still_passes_report_v11()
    assert report["verdict"] == "PASS"
    assert report["order_creating_endpoints_called"] == []
