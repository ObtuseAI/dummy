from __future__ import annotations

from scripts.generate_v13_reports import generate_no_llm_secret_leak_report_v13


def test_no_llm_secret_leak_v13_report_passes() -> None:
    report = generate_no_llm_secret_leak_report_v13()

    assert report["verdict"] == "PASS"
    assert report["kalshi_secret_values_sent_to_llm"] is False
