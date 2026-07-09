from __future__ import annotations

from scripts.generate_v12_reports import generate_no_secret_leak_report_v12


def test_no_secret_leak_v12() -> None:
    report = generate_no_secret_leak_report_v12()

    assert report["verdict"] == "PASS"
    assert report["leaked_files"] == []
