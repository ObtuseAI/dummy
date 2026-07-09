from __future__ import annotations


def test_no_llm_secret_leak_v19_report_passes() -> None:
    from scripts.generate_v19_reports import generate_no_llm_secret_leak_report_v19

    report = generate_no_llm_secret_leak_report_v19()
    assert report["llm_receives_credentials"] is False
    assert report["verdict"] == "PASS"
