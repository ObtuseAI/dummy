from __future__ import annotations


def test_no_kalshi_private_key_leak_v19_report_passes() -> None:
    from archive.report_scripts.generate_v19_reports import generate_no_kalshi_private_key_leak_report_v19

    report = generate_no_kalshi_private_key_leak_report_v19()
    assert report["private_key_material_found"] is False
    assert report["verdict"] == "PASS"
