from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from model_router.config import ProviderConfig
from model_router.providers import (
    DeepSeekV4FlashProvider,
    MinimaxM3Provider,
    MockProvider,
)
from model_router.tasks import ModelTask


@pytest.fixture
def mock_config() -> ProviderConfig:
    return ProviderConfig(
        api_base="https://openrouter.ai/api/v1",
        api_key_env="TEST_API_KEY",
        model_name="test/model",
        timeout_seconds=5.0,
    )


def _expected_digest(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


@pytest.mark.asyncio
async def test_mock_provider_returns_tuple_and_metadata():
    provider = MockProvider()
    prompt = "forecast prompt"
    content, metadata = await provider.complete(prompt, ModelTask.FORECAST_OPINION)

    assert isinstance(content, str)
    assert isinstance(metadata, dict)
    assert metadata["provider"] == "mock"
    assert metadata["model"] == "mock"
    assert metadata["attempts"] == 1
    assert metadata["error_class"] is None
    assert metadata["cost_usd"] == 0.0
    assert metadata["prompt_digest"] == _expected_digest(prompt)
    assert metadata["latency_ms"] >= 0

    data = json.loads(content)
    assert "dummy_probability" in data
    assert "confidence_score" in data
    assert "reasoning" in data


@pytest.mark.asyncio
async def test_mock_provider_covers_all_tasks():
    provider = MockProvider()
    for task in ModelTask:
        content, metadata = await provider.complete(f"prompt for {task.value}", task)
        assert json.loads(content)
        assert metadata["error_class"] is None


@pytest.mark.asyncio
async def test_mock_provider_never_includes_raw_prompt():
    provider = MockProvider()
    prompt = "very secret prompt content"
    _, metadata = await provider.complete(prompt, ModelTask.STRATEGY_CRITIQUE)
    assert prompt not in str(metadata)
    assert metadata["prompt_digest"] == _expected_digest(prompt)


_TASK_CONTENT = {
    ModelTask.FORECAST_OPINION: {"dummy_probability": "0.55", "confidence_score": "0.72", "reasoning": "ok"},
    ModelTask.STRATEGY_CRITIQUE: {"verdict": "proceed", "reasoning": "ok"},
    ModelTask.RISK_CRITIQUE: {"risk_level": "low", "reasoning": "ok"},
    ModelTask.NO_TRADE_REASON: {"reason": "mock", "contributing_factors": ["x"]},
    ModelTask.TRADE_DRAFT: {"action": "hold", "reasoning": "ok"},
    ModelTask.CALIBRATION_NOTE: {"note": "ok"},
    ModelTask.MARKET_THESIS: {"thesis": "ok", "confidence": "0.6"},
    ModelTask.HYBRID_REVIEW: {"verdict": "agree", "agreement_score": "0.8"},
}


def _make_post_mock(task: ModelTask = ModelTask.FORECAST_OPINION, response_json: dict | None = None, status_code: int = 200, side_effect=None):
    """Return a patched httpx.AsyncClient that yields the configured response."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = response_json or {
        "choices": [{"message": {"content": json.dumps(_TASK_CONTENT[task])}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    response.raise_for_status = MagicMock()

    post_mock = AsyncMock(return_value=response)
    if side_effect is not None:
        post_mock.side_effect = side_effect

    client_instance = MagicMock()
    client_instance.post = post_mock
    client_instance.__aenter__ = AsyncMock(return_value=client_instance)
    client_instance.__aexit__ = AsyncMock(return_value=False)

    client_class = MagicMock(return_value=client_instance)
    return client_class, post_mock


@pytest.mark.asyncio
async def test_deepseek_provider_success(mock_config, monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    provider = DeepSeekV4FlashProvider(mock_config)

    client_class, post_mock = _make_post_mock()
    with patch("model_router.providers.httpx.AsyncClient", client_class):
        content, metadata = await provider.complete("prompt", ModelTask.FORECAST_OPINION)

    assert json.loads(content)["dummy_probability"] == "0.55"
    assert metadata["provider"] == "deepseek_v4_flash"
    assert metadata["model"] == "test/model"
    assert metadata["attempts"] == 1
    assert metadata["error_class"] is None
    assert metadata["cost_usd"] is not None
    assert metadata["prompt_digest"] == _expected_digest("prompt")
    assert post_mock.await_count == 1
    _, kwargs = post_mock.await_args
    assert kwargs["headers"]["Authorization"].startswith("Bearer ")
    assert "sk-test" not in str(metadata)


@pytest.mark.asyncio
async def test_minimax_provider_success(mock_config, monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    provider = MinimaxM3Provider(mock_config)

    client_class, post_mock = _make_post_mock(task=ModelTask.STRATEGY_CRITIQUE)
    with patch("model_router.providers.httpx.AsyncClient", client_class):
        content, metadata = await provider.complete("prompt", ModelTask.STRATEGY_CRITIQUE)

    data = json.loads(content)
    assert "verdict" in data
    assert metadata["provider"] == "minimax_m3"
    assert metadata["attempts"] == 1


@pytest.mark.asyncio
async def test_deepseek_provider_reads_env_overrides(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-env-model")

    cfg = ProviderConfig(
        api_base="https://openrouter.ai/api/v1",
        api_key_env="DEEPSEEK_API_KEY",
        model_name="deepseek/config",
    )
    provider = DeepSeekV4FlashProvider(cfg)

    client_class, post_mock = _make_post_mock()
    with patch("model_router.providers.httpx.AsyncClient", client_class):
        _, metadata = await provider.complete("prompt", ModelTask.FORECAST_OPINION)

    assert metadata["model"] == "deepseek-env-model"
    call_url = post_mock.await_args[0][0]
    assert call_url.startswith("https://api.deepseek.test")


@pytest.mark.asyncio
async def test_provider_unavailable_without_key(mock_config, monkeypatch):
    monkeypatch.delenv("TEST_API_KEY", raising=False)
    provider = DeepSeekV4FlashProvider(mock_config)
    assert not provider.available
