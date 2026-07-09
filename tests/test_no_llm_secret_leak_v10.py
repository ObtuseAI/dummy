from __future__ import annotations

from scripts.generate_v10_reports import generate_no_llm_secret_leak_report_v10


def test_no_llm_secret_leak_v10(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-v10-secret")
    report = generate_no_llm_secret_leak_report_v10()
    assert report["verdict"] == "PASS"
    assert report["leaked"] is False
