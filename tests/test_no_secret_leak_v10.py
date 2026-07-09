from __future__ import annotations

from scripts.generate_v10_reports import generate_no_secret_leak_report_v10


def test_no_secret_leak_v10() -> None:
    report = generate_no_secret_leak_report_v10()
    assert report["verdict"] == "PASS"
    assert report["leaked_files"] == []
