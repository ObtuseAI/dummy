from __future__ import annotations

import pytest

from archive.report_scripts.generate_v8_1_reports import generate_model_provider_config_audit_report_v1


def test_config_audit_report_has_no_secret_values(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-value")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-secret-value")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-secret-value")

    report = generate_model_provider_config_audit_report_v1()
    text = str(report)

    assert "sk-deepseek-secret-value" not in text
    assert "sk-minimax-secret-value" not in text
    assert "sk-openrouter-secret-value" not in text
    assert report["verdict"] == "PASS"
    for provider in ("deepseek_v4_flash", "minimax_m3"):
        entry = report[provider]
        assert entry["api_key_present"] is True
        assert entry["api_key_env"] == "OPENROUTER_API_KEY"
        assert entry["api_base"].startswith("https://")
        assert entry["configured_model"]
        assert entry["alias_count"] >= 1


def test_config_audit_report_redacts_api_key_absence(monkeypatch, no_project_env):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    report = generate_model_provider_config_audit_report_v1()
    for provider in ("deepseek_v4_flash", "minimax_m3"):
        assert report[provider]["api_key_present"] is False
    assert report["verdict"] == "PASS"
