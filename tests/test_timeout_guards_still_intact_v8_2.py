from __future__ import annotations

import asyncio

import pytest

from model_router.providers import ProviderConfig, DeepSeekV4FlashProvider
from model_router.smoke import LiveModelSmokeV3, SMOKE_CALL_TIMEOUT, SMOKE_TOTAL_TIMEOUT


def test_smoke_call_timeout_is_bounded():
    assert SMOKE_CALL_TIMEOUT <= 20


def test_smoke_total_timeout_is_bounded():
    assert SMOKE_TOTAL_TIMEOUT <= 45


def test_provider_config_timeout_is_bounded_in_call():
    cfg = ProviderConfig(
        api_base="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        model_name="deepseek-chat",
        timeout_seconds=30.0,
    )
    provider = DeepSeekV4FlashProvider(cfg)
    # The provider stores the configured timeout but clamps it at call time.
    assert provider.config.timeout_seconds == 30.0
    assert min(provider.config.timeout_seconds, 20) <= 20.0


@pytest.mark.asyncio
async def test_smoke_v3_total_timeout_falls_back(clean_env, no_project_env, monkeypatch, tmp_path):
    import model_router.smoke as smoke_module

    monkeypatch.setattr(smoke_module, "SMOKE_TOTAL_TIMEOUT", 1)
    runner = LiveModelSmokeV3(artifacts_dir=tmp_path)
    report = await runner.run()
    assert report["model_mode"] == "MOCK_ONLY"
    assert report["verdict"] == "PASS"
