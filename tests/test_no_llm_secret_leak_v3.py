from __future__ import annotations

import json

import pytest

from scripts.generate_v8_1_reports import generate_no_llm_secret_leak_report_v3


def test_no_llm_secret_leak_report_passes_with_clean_prompts(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-value")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-secret-value")

    report = generate_no_llm_secret_leak_report_v3()
    assert report["verdict"] == "PASS"
    assert report["leaked"] is False


def test_no_llm_secret_leak_report_detects_secret_in_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-value")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-secret-value")

    # Inject a prompt that contains the secret by temporarily patching the module constant.
    import model_router.smoke as smoke_module

    original = smoke_module._DEEPSEEK_SMOKE_PROMPT
    monkeypatch.setattr(smoke_module, "_DEEPSEEK_SMOKE_PROMPT", original + " sk-deepseek-secret-value")
    report = generate_no_llm_secret_leak_report_v3()
    assert report["verdict"] == "FAIL"
    assert report["leaked"] is True
