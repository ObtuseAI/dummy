from __future__ import annotations


def test_no_kalshi_private_key_leak_v18_report_passes() -> None:
    from scripts.generate_v18_reports import generate_no_kalshi_private_key_leak_report_v18

    report = generate_no_kalshi_private_key_leak_report_v18()
    assert report["private_key_material_found"] is False
    assert report["verdict"] == "PASS"
