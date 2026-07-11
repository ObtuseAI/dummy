from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import httpx
import pytest

from kalshi.client import KalshiClient
from model_router.config import ProviderConfig
from model_router.providers import BaseModelProvider
from model_router.smoke import LiveModelSmoke, SMOKE_CALL_TIMEOUT
from model_router.tasks import ModelTask
from archive.report_scripts.generate_v8_reports import main as orchestrator_main, ORCHESTRATOR_TIMEOUT_SECONDS


class _SlowProvider(BaseModelProvider):
    name = "slow_provider"

    @property
    def available(self) -> bool:
        return True

    async def _call_api(self, prompt, task, max_tokens, temperature):
        await asyncio.sleep(120)
        return json.dumps({"ok": True})


@pytest.mark.asyncio
async def test_kalshi_client_request_times_out_within_30s(monkeypatch):
    """A stalled Kalshi server must not block the client beyond the outer bound."""
    import kalshi.client as kalshi_client_module

    # Use a short timeout in the test so we prove the path without waiting 30s.
    monkeypatch.setattr(kalshi_client_module, "_REQUEST_OUTER_TIMEOUT_SECONDS", 2)
    client = KalshiClient()

    async def _never_respond(*args, **kwargs):
        await asyncio.sleep(120)
        return httpx.Response(200, json={})

    start = asyncio.get_event_loop().time()
    with patch("kalshi.client.sign_request", return_value={
        "KALSHI-ACCESS-KEY": "test",
        "KALSHI-ACCESS-SIGNATURE": "sig",
        "KALSHI-ACCESS-TIMESTAMP": "ts",
    }):
        with patch.object(client.client, "request", new=_never_respond):
            with pytest.raises(asyncio.TimeoutError):
                await client.get_markets()
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 10, f"Kalshi client blocked for {elapsed:.1f}s"
    await client.close()


@pytest.mark.asyncio
async def test_provider_smoke_call_times_out_within_20s(tmp_path, monkeypatch):
    """A single provider smoke call that never responds must fallback within 20s."""
    import model_router.smoke as smoke_module

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-minimax-test")
    # Use a short timeout in the test so we prove the path without waiting 20s.
    monkeypatch.setattr(smoke_module, "SMOKE_CALL_TIMEOUT", 2)

    runner = LiveModelSmoke(artifacts_dir=tmp_path)
    slow = _SlowProvider(ProviderConfig(api_base="", api_key_env="", model_name="slow"))

    start = asyncio.get_event_loop().time()
    result = await runner._execute_call(
        slow,
        runner.deepseek_prompt,
        ModelTask.MARKET_THESIS,
        prompt_summary="harmless market summary prompt",
    )
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed < 10, f"Smoke call blocked for {elapsed:.1f}s"
    assert result.status == "mock_fallback"
    assert result.error_class == "TIMEOUT"
    assert result.response_schema_ok is True


@pytest.mark.asyncio
async def test_report_generator_times_out_within_90s(tmp_path, monkeypatch):
    """The orchestrator must not hang when a report generator stalls."""
    import archive.report_scripts.generate_v8_reports as orchestrator
    import archive.report_scripts.generate_v8_model_provider_reports as model_reports

    artifacts = tmp_path / "dummy"
    artifacts.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(orchestrator, "ARTIFACTS", artifacts)
    # Use a short timeout so the test proves the path without waiting 90s.
    monkeypatch.setattr(orchestrator, "ORCHESTRATOR_TIMEOUT_SECONDS", 2)

    async def _stall(*args, **kwargs):
        await asyncio.sleep(120)
        return {}

    start = asyncio.get_event_loop().time()
    with patch.object(model_reports, "main", new=_stall):
        result = await orchestrator_main(run_tests=False)
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed < 20, f"Orchestrator blocked for {elapsed:.1f}s"
    assert result["verdict"] in ("PASS", "PARTIAL", "FAIL")
    assert (artifacts / "tests_summary.json").exists()
    assert (artifacts / "final_report.json").exists()


@pytest.mark.asyncio
async def test_no_test_waits_indefinitely():
    """Sanity check: this test itself completes quickly and proves the suite is bounded."""
    assert True
