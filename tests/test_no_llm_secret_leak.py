from __future__ import annotations

import pytest

from model_router.router import ModelRouter
from model_router.tasks import ModelTask


@pytest.mark.asyncio
async def test_prompt_redacts_secret(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-1234567890abcdef")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-secret-1234567890abcdef")
    router = ModelRouter()
    prompt = "Analyze with key sk-deepseek-secret-1234567890abcdef"
    envelope = await router.call(ModelTask.FORECAST_OPINION, prompt)
    assert "sk-deepseek-secret" not in envelope.prompt
    assert "***REDACTED***" in envelope.prompt
    assert "sk-deepseek-secret" not in envelope.content
    assert "sk-minimax-secret" not in envelope.content


@pytest.mark.asyncio
async def test_minimax_secret_not_leaked_through_content(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-secret-1234567890abcdef")
    router = ModelRouter()
    envelope = await router.call(ModelTask.STRATEGY_CRITIQUE, "Use minimax sk-minimax-secret-1234567890abcdef")
    assert "sk-minimax-secret" not in envelope.prompt
    assert "sk-minimax-secret" not in envelope.content
    assert "***REDACTED***" in envelope.prompt


@pytest.mark.asyncio
async def test_raw_metadata_does_not_contain_api_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-1234567890abcdef")
    router = ModelRouter()
    envelope = await router.call(ModelTask.FORECAST_OPINION, "What is the probability?")
    raw = str(envelope.raw_metadata)
    assert "sk-deepseek-secret" not in raw
    assert "DEEPSEEK_API_KEY" not in raw


@pytest.mark.asyncio
async def test_blocked_secret_prompt_is_redacted_and_blocked(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-1234567890abcdef")
    router = ModelRouter()
    envelope = await router.call(ModelTask.FORECAST_OPINION, "my key is sk-deepseek-secret-1234567890abcdef")
    assert envelope.blocked_by == "secret_leak"
    assert "sk-deepseek-secret" not in envelope.prompt
    assert "***REDACTED***" in envelope.prompt
