from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from model_router.smoke import LiveModelSmokeV2


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


@pytest.fixture
def smoke_v2_runner(tmp_path):
    return LiveModelSmokeV2(artifacts_dir=tmp_path)


@pytest.mark.asyncio
async def test_smoke_v2_mock_only_without_credentials(clean_env, no_project_env, smoke_v2_runner):
    report = await smoke_v2_runner.run()

    assert report["live_model_status"] == "MOCK_ONLY"
    assert report["model_mode"] == "MOCK_ONLY"
    assert report["verdict"] == "PASS"
    for r in report["call_results"]:
        assert r["status"] == "MOCK_ONLY"
        assert r["prompt_firewall_ok"] is True
        assert r["output_firewall_ok"] is True
        assert r["secret_free"] is True


@pytest.mark.asyncio
async def test_smoke_v2_live_proven_with_resolution(monkeypatch, smoke_v2_runner):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")

    async def _fake_resolve(self, *args, **kwargs):
        from model_router.resolver import ProviderResolutionResult

        return ProviderResolutionResult(
            provider_name=args[0],
            status="LIVE_PROVEN",
            api_base="https://api.example.com",
            api_key_env="TEST_API_KEY",
            configured_model="test-model",
            resolved_model="test-model",
            resolved_by="model_list",
        )

    async def _fake_complete(prompt, task, **kwargs):
        if task.value == "market_thesis":
            return (
                json.dumps({"thesis": "neutral", "confidence": "0.5"}),
                {"provider": "deepseek", "model": "test-model", "latency_ms": 10.0, "attempts": 1, "prompt_digest": "abc"},
            )
        return (
            json.dumps({"risk_level": "low", "reasoning": "calm"}),
            {"provider": "minimax", "model": "test-model", "latency_ms": 10.0, "attempts": 1, "prompt_digest": "def"},
        )

    with patch("model_router.smoke.ModelProviderResolver.resolve", new=_fake_resolve):
        with patch.object(smoke_v2_runner, "_build_resolved_provider") as mock_build:
            fake_provider = AsyncMock()
            fake_provider.complete = _fake_complete
            fake_provider.name = "test_provider"
            mock_build.return_value = fake_provider
            report = await smoke_v2_runner.run()

    assert report["live_model_status"] == "LIVE_PROVEN"
    assert report["model_mode"] == "LIVE_PROVEN"
    assert report["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_smoke_v2_operator_config_required_on_404(monkeypatch, smoke_v2_runner):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")

    async def _fake_resolve(self, *args, **kwargs):
        from model_router.resolver import ProviderResolutionResult

        return ProviderResolutionResult(
            provider_name=args[0],
            status="OPERATOR_MODEL_CONFIG_REQUIRED",
            api_base="https://api.example.com",
            api_key_env="TEST_API_KEY",
            configured_model="unknown-model",
            error_category="MODEL_NOT_FOUND",
            error_detail="all aliases unresolved",
        )

    with patch("model_router.smoke.ModelProviderResolver.resolve", new=_fake_resolve):
        report = await smoke_v2_runner.run()

    assert report["live_model_status"] == "OPERATOR_MODEL_CONFIG_REQUIRED"
    assert report["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_smoke_v2_reports_no_raw_prompts_or_keys(clean_env, smoke_v2_runner, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-secret-value")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-secret-value")

    report = await smoke_v2_runner.run()
    text = json.dumps(report, default=str)

    assert smoke_v2_runner.deepseek_prompt not in text
    assert smoke_v2_runner.minimax_prompt not in text
    assert "sk-deepseek-secret-value" not in text
    assert "sk-minimax-secret-value" not in text


@pytest.mark.asyncio
async def test_smoke_v2_total_timeout_is_bounded(clean_env, no_project_env, monkeypatch, smoke_v2_runner):
    import asyncio
    import model_router.smoke as smoke_module

    monkeypatch.setattr(smoke_module, "SMOKE_TOTAL_TIMEOUT", 1)

    report = await smoke_v2_runner.run()
    assert report["model_mode"] == "MOCK_ONLY"
    assert report["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_smoke_v2_writes_v2_reports(clean_env, tmp_path):
    runner = LiveModelSmokeV2(artifacts_dir=tmp_path)
    report = await runner.run()
    paths = await runner.write_reports_v2(report)

    assert "live_model_smoke_report_v2.json" in paths
    assert "live_model_prompt_safety_report_v2.json" in paths
    assert "live_model_output_safety_report_v1.json" in paths
    for path in paths.values():
        assert path.exists()
