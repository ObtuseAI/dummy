from __future__ import annotations

from scripts.generate_v9_reports import generate_no_llm_secret_leak_report_v9


def test_no_llm_secret_leak_v9_passes_with_clean_prompts(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-secret-value")
    report = generate_no_llm_secret_leak_report_v9()
    assert report["verdict"] == "PASS"
    assert report["leaked"] is False


def test_no_llm_secret_leak_v9_detects_secret_in_prompt(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-secret-value")

    import model_router.smoke as smoke_module

    original = smoke_module._DEEPSEEK_SMOKE_PROMPT
    monkeypatch.setattr(
        smoke_module,
        "_DEEPSEEK_SMOKE_PROMPT",
        original + " sk-openrouter-secret-value",
    )

    report = generate_no_llm_secret_leak_report_v9()
    assert report["verdict"] == "FAIL"
    assert report["leaked"] is True
