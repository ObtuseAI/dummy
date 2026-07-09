from __future__ import annotations

from model_router.credential_source import (
    ProviderCredentialReadinessV2,
    ProviderCredentialSource,
    ProviderCredentialSourceResolver,
)


def test_resolver_detects_process_env_first(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-process")
    resolver = ProviderCredentialSourceResolver()
    resolution = resolver.resolve("DEEPSEEK_API_KEY")
    assert resolution.present is True
    assert resolution.source == ProviderCredentialSource.PROCESS_ENV


def test_readiness_v2_returns_redacted_status(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
    readiness = ProviderCredentialReadinessV2()
    ds = readiness.deepseek_status()
    assert ds.present is True
    assert ds.redacted is True
    assert "sk-test" not in str(ds.as_dict())


def test_readiness_v2_ready_requires_named_keys(monkeypatch, no_project_env):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    readiness = ProviderCredentialReadinessV2()
    assert readiness.ready(["DEEPSEEK_API_KEY"]) is True
    assert readiness.ready(["DEEPSEEK_API_KEY", "MINIMAX_API_KEY"]) is False
