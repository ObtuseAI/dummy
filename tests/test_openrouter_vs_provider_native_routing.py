from __future__ import annotations

from model_router.route_mode import ProviderRouteModeResolver


def test_openrouter_prefers_openrouter_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-test")
    resolver = ProviderRouteModeResolver()
    result = resolver.resolve(
        "deepseek_v4_flash", "https://openrouter.ai/api", "deepseek/deepseek-v3"
    )
    assert result.intended_key_env == "OPENROUTER_API_KEY"
    assert result.key_present is True


def test_native_deepseek_uses_deepseek_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    resolver = ProviderRouteModeResolver()
    result = resolver.resolve(
        "deepseek_v4_flash", "https://api.deepseek.com", "deepseek-chat"
    )
    assert result.intended_key_env == "DEEPSEEK_API_KEY"
    assert result.key_present is True


def test_native_minimax_uses_minimax_key(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-mm-test")
    resolver = ProviderRouteModeResolver()
    result = resolver.resolve(
        "minimax_m3", "https://api.minimax.chat", "minimax-01"
    )
    assert result.intended_key_env == "MINIMAX_API_KEY"
    assert result.key_present is True


def test_openrouter_reports_missing_openrouter_key(monkeypatch, no_project_env):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-test")
    resolver = ProviderRouteModeResolver()
    result = resolver.resolve(
        "deepseek_v4_flash", "https://openrouter.ai/api", "deepseek/deepseek-v3"
    )
    assert result.intended_key_env == "OPENROUTER_API_KEY"
    assert result.key_present is False
