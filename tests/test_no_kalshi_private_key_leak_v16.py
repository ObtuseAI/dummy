from __future__ import annotations


def test_no_kalshi_private_key_leak_v16_report_passes() -> None:
    from archive.report_scripts.generate_v16_reports import generate_no_kalshi_private_key_leak_report_v16

    assert generate_no_kalshi_private_key_leak_report_v16()["verdict"] == "PASS"
