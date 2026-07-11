from __future__ import annotations

from archive.report_scripts.generate_v14_reports import generate_no_kalshi_private_key_leak_report_v14


def test_no_kalshi_private_key_leak_v14_report_passes() -> None:
    report = generate_no_kalshi_private_key_leak_report_v14()

    assert report["private_key_material_found"] is False
    assert report["verdict"] == "PASS"
