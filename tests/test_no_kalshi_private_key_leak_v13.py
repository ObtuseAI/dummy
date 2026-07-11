from __future__ import annotations

from archive.report_scripts.generate_v13_reports import generate_no_kalshi_private_key_leak_report_v13


def test_no_kalshi_private_key_leak_v13_report_passes() -> None:
    report = generate_no_kalshi_private_key_leak_report_v13()

    assert report["verdict"] == "PASS"
    assert report["private_key_material_found"] is False
