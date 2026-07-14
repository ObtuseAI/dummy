from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from model_router.config import ProviderConfig
from model_router.providers import DeepSeekV4FlashProvider, MinimaxM3Provider
from model_router.tasks import ModelTask


class _CapturingClient:
    """Capture the ``timeout`` kwarg passed to ``httpx.AsyncClient``."""

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        response = MagicMock()
        response.status_code = 200
        # Superset of keys satisfies every task schema used in the guard tests.
        response.json.return_value = {
            "choices": [{
                "message": {
                    "content": (
                        '{"dummy_probability":"0.55","confidence_score":"0.72","reasoning":"ok",'
                        '"verdict":"proceed","risk_level":"low","action":"hold","note":"ok",'
                        '"thesis":"ok","agreement_score":"0.8","contributing_factors":["x"]}'
                    ),
                },
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        response.raise_for_status = MagicMock()
        return response


def test_provider_config_default_timeout_is_at_most_20s():
    """The default provider timeout must not exceed the 20s hard ceiling."""
    cfg = ProviderConfig(api_base="https://api.example.com", api_key_env="TEST_KEY", model_name="test")
    assert cfg.timeout_seconds <= 20.0


@pytest.mark.asyncio
async def test_deepseek_http_timeout_is_capped_at_20s(monkeypatch):
    """DeepSeekV4FlashProvider passes a timeout <= 20s to httpx."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    cfg = ProviderConfig(
        api_base="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        model_name="deepseekv4flash",
        timeout_seconds=30.0,
    )
    provider = DeepSeekV4FlashProvider(cfg)

    captured = {}

    def _client_factory(*, timeout, **kwargs):
        captured["timeout"] = timeout
        return _CapturingClient(timeout)

    with patch("model_router.providers.httpx.AsyncClient", new=_client_factory):
        await provider.complete("test", ModelTask.FORECAST_OPINION)

    assert captured["timeout"] <= 20.0


@pytest.mark.asyncio
async def test_minimax_http_timeout_is_capped_at_20s(monkeypatch):
    """MinimaxM3Provider passes a timeout <= 20s to httpx."""
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
    cfg = ProviderConfig(
        api_base="https://api.minimax.chat",
        api_key_env="MINIMAX_API_KEY",
        model_name="minimaxm3",
        timeout_seconds=30.0,
    )
    provider = MinimaxM3Provider(cfg)

    captured = {}

    def _client_factory(*, timeout, **kwargs):
        captured["timeout"] = timeout
        return _CapturingClient(timeout)

    with patch("model_router.providers.httpx.AsyncClient", new=_client_factory):
        await provider.complete("test", ModelTask.STRATEGY_CRITIQUE)

    assert captured["timeout"] <= 20.0


@pytest.mark.asyncio
async def test_provider_complete_does_not_wait_indefinitely(monkeypatch):
    """A failing provider call must surface promptly without blocking forever."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    cfg = ProviderConfig(
        api_base="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        model_name="deepseekv4flash",
        timeout_seconds=1.0,
    )
    provider = DeepSeekV4FlashProvider(cfg)

    async def _fail_fast(*args, **kwargs):
        raise RuntimeError("simulated provider failure")

    start = asyncio.get_event_loop().time()
    with patch.object(provider, "_call_api", new=_fail_fast):
        with pytest.raises(Exception):  # ProviderError
            await provider.complete("test", ModelTask.FORECAST_OPINION)
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 10, f"provider.complete blocked for {elapsed:.1f}s"
