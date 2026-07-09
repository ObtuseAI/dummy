from __future__ import annotations

from scripts.generate_v11_reports import generate_no_llm_secret_leak_report_v11


def test_no_llm_secret_leak_v11() -> None:
    report = generate_no_llm_secret_leak_report_v11()
    assert report["verdict"] == "PASS"
    assert report["leaked"] is False
