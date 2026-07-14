from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import patch

import pytest

from model_router.config import ProviderConfig
from model_router.providers import BaseModelProvider, MockProvider
from model_router.smoke import LiveModelSmoke, generate_live_model_smoke_report_v1
from model_router.tasks import ModelTask


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)


@pytest.fixture
def smoke_runner(tmp_path):
    return LiveModelSmoke(artifacts_dir=tmp_path)


@pytest.mark.asyncio
async def test_smoke_run_returns_mock_only_without_credentials(
    clean_env, smoke_runner
):
    report = await smoke_runner.run()

    assert report["live_model_status"] == "MOCK_ONLY"
    assert report["model_mode"] == "MOCK_ONLY"
    assert report["verdict"] == "PASS"
    assert report["credential_status"]["all_ready"] is False
    assert report["credential_status"]["deepseek"]["present"] is False
    assert report["credential_status"]["minimax"]["present"] is False


@pytest.mark.asyncio
async def test_smoke_run_records_call_results_without_credentials(
    clean_env, smoke_runner
):
    report = await smoke_runner.run()
    results = report["call_results"]

    assert len(results) == 2
    by_provider = {r["provider"]: r for r in results}
    assert "mock" in by_provider

    for r in results:
        assert r["status"] == "ok"
        assert r["response_schema_ok"] is True
        assert r["firewall_ok"] is True
        assert r["order_instruction_free"] is True
        assert r["secret_free"] is True
        assert r["error_class"] is None
        assert "latency_ms" in r
        assert "attempts" in r
        assert "prompt_digest" in r
        assert "prompt_summary" in r
        assert "model" in r


@pytest.mark.asyncio
async def test_smoke_run_with_credentials_attempts_live_success(
    monkeypatch, smoke_runner
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-test")

    async def _fake_complete(self, prompt, task, **kwargs):
        if task is ModelTask.MARKET_THESIS:
            return (
                json.dumps({"thesis": "neutral", "confidence": "0.5"}),
                {
                    "provider": "deepseek_v4_flash",
                    "model": "deepseek/deepseek-v3",
                    "latency_ms": 123.0,
                    "attempts": 1,
                    "prompt_digest": "deadbeef",
                    "error_class": None,
                    "cost_usd": 0.0,
                },
            )
        return (
            json.dumps({"risk_level": "low", "reasoning": "calm markets"}),
            {
                "provider": "minimax_m3",
                "model": "minimax/minimax-01",
                "latency_ms": 456.0,
                "attempts": 1,
                "prompt_digest": "cafebabe",
                "error_class": None,
                "cost_usd": 0.0,
            },
        )

    with patch.object(
        smoke_runner, "_build_provider", return_value=MockProvider()
    ), patch.object(MockProvider, "complete", new=_fake_complete):
        report = await smoke_runner.run()

    assert report["live_model_status"] == "LIVE"
    assert report["model_mode"] == "LIVE"
    assert report["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_smoke_run_with_credentials_live_failure_falls_back_to_mock(
    monkeypatch, smoke_runner
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-test")

    class _FailingProvider(BaseModelProvider):
        name = "failing_provider"

        @property
        def available(self) -> bool:
            return True

        async def _call_api(self, prompt, task, max_tokens, temperature):
            from model_router.providers import ProviderError

            raise ProviderError(
                "simulated failure",
                metadata={
                    "provider": self.name,
                    "model": "test-model",
                    "latency_ms": 12.0,
                    "attempts": 1,
                    "prompt_digest": "deadbeef",
                    "error_class": "HTTP_500",
                    "cost_usd": None,
                },
            )

    failing = _FailingProvider(ProviderConfig(api_base="", api_key_env="", model_name="failing"))
    with patch.object(smoke_runner, "_build_provider", return_value=failing):
        report = await smoke_runner.run()

    assert report["live_model_status"] == "MOCK_ONLY"
    assert report["model_mode"] == "MOCK_ONLY"
    assert report["verdict"] == "PASS"
    for r in report["call_results"]:
        assert r["status"] == "mock_fallback"
        assert r["response_schema_ok"] is True
        assert r["error_class"] in ("HTTP_500", "PROVIDER_ERROR")


@pytest.mark.asyncio
async def test_smoke_reports_no_raw_prompts_or_api_keys(
    clean_env, smoke_runner, monkeypatch
):
    report = await smoke_runner.run()
    report_text = json.dumps(report, default=str)

    assert smoke_runner.deepseek_prompt not in report_text
    assert smoke_runner.minimax_prompt not in report_text
    assert "sk-deepseek" not in report_text
    assert "sk-minimax" not in report_text

    for value in os.environ.values():
        if value and len(value) >= 8 and "sk-" in value:
            assert value not in report_text


@pytest.mark.asyncio
async def test_smoke_report_generation_writes_files_without_credentials(
    clean_env, tmp_path
):
    runner = LiveModelSmoke(artifacts_dir=tmp_path)
    report = await runner.run()
    paths = runner.write_reports(report)

    assert "live_model_smoke_report_v1.json" in paths
    assert "live_model_prompt_safety_report_v1.json" in paths
    for path in paths.values():
        assert path.exists()
        text = path.read_text()
        assert "sk-" not in text
        assert runner.deepseek_prompt not in text
        assert runner.minimax_prompt not in text


@pytest.mark.asyncio
async def test_public_generate_smoke_report_helper(clean_env):
    report = await generate_live_model_smoke_report_v1()
    assert report["live_model_status"] == "MOCK_ONLY"
    assert report["model_mode"] == "MOCK_ONLY"
    assert report["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_smoke_run_falls_back_to_mock_on_provider_timeout(
    monkeypatch, smoke_runner
):
    import model_router.smoke as smoke_module

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-test")
    monkeypatch.setattr(smoke_module, "SMOKE_CALL_TIMEOUT", 2)

    class _SlowProvider(BaseModelProvider):
        name = "slow_provider"

        @property
        def available(self) -> bool:
            return True

        async def _call_api(self, prompt, task, max_tokens, temperature):
            await asyncio.sleep(60)
            return json.dumps({"ok": True})

    slow = _SlowProvider(ProviderConfig(api_base="", api_key_env="", model_name="slow"))
    start = asyncio.get_event_loop().time()
    result = await smoke_runner._execute_call(
        slow,
        smoke_runner.deepseek_prompt,
        ModelTask.MARKET_THESIS,
        prompt_summary="harmless market summary prompt",
    )
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed < 10, f"Smoke fallback blocked for {elapsed:.1f}s"
    assert result.status == "mock_fallback"
    assert result.error_class == "TIMEOUT"
    assert result.response_schema_ok is True
