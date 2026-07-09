from __future__ import annotations

from scripts.generate_v14_reports import generate_no_secret_leak_report_v14


def test_no_secret_leak_v14_report_passes() -> None:
    report = generate_no_secret_leak_report_v14()

    assert report["verdict"] == "PASS"
    assert report["leaked_files"] == []
