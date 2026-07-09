from __future__ import annotations

import os

import pytest

from model_router.router import ModelRouter
from model_router.tasks import ModelTask


@pytest.mark.asyncio
async def test_mock_fallback_no_keys():
    router = ModelRouter()
    envelope = await router.call(ModelTask.FORECAST_OPINION, "What is the probability?")
    assert envelope.decision.provider_name == "mock"
    assert envelope.blocked_by is None
    assert envelope.content
    assert envelope.proof_id


@pytest.mark.asyncio
async def test_mock_fallback_for_each_task():
    router = ModelRouter()
    for task in ModelTask:
        envelope = await router.call(task, f"Task prompt for {task.value}")
        assert envelope.decision.provider_name == "mock"
        assert envelope.blocked_by is None
        assert envelope.content


@pytest.mark.asyncio
async def test_hybrid_review_resolves_to_deepseek_when_available(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-test")
    router = ModelRouter()
    decision = router.route(ModelTask.HYBRID_REVIEW)
    assert decision.provider_name == "deepseek_v4_flash"
    assert decision.model_name == "deepseek/deepseek-chat"


@pytest.mark.asyncio
async def test_hybrid_review_fallback_when_deepseek_unavailable(monkeypatch, no_project_env):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    router = ModelRouter()
    decision = router.route(ModelTask.HYBRID_REVIEW)
    assert decision.provider_name == "mock"
    assert decision.fallback_reason == "deepseek_v4_flash_credentials_missing"


@pytest.mark.asyncio
async def test_preferred_provider_used_when_key_present(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-test")
    router = ModelRouter()

    assert router.route(ModelTask.FORECAST_OPINION).provider_name == "deepseek_v4_flash"
    assert router.route(ModelTask.STRATEGY_CRITIQUE).provider_name == "minimax_m3"
    assert router.route(ModelTask.RISK_CRITIQUE).provider_name == "deepseek_v4_flash"
    assert router.route(ModelTask.NO_TRADE_REASON).provider_name == "minimax_m3"


@pytest.mark.asyncio
async def test_cost_tracker_records_calls():
    router = ModelRouter()
    before = router.cost_tracker.calls
    await router.call(ModelTask.FORECAST_OPINION, "prompt")
    assert router.cost_tracker.calls == before + 1
    summary = router.cost_tracker.summary()
    assert summary["calls"] == router.cost_tracker.calls
    assert summary["avg_latency_ms"] >= 0


@pytest.mark.asyncio
async def test_blocked_prompt_not_routed():
    router = ModelRouter()
    envelope = await router.call(ModelTask.TRADE_DRAFT, "Please create_order(foo)")
    assert envelope.blocked_by == "order_endpoint"
    assert envelope.decision.provider_name == "none"
    assert envelope.content == ""


@pytest.mark.asyncio
async def test_router_uses_sanitized_prompt_in_envelope():
    router = ModelRouter()
    prompt = "  hello\x00world   "
    envelope = await router.call(ModelTask.FORECAST_OPINION, prompt)
    assert "\x00" not in envelope.prompt
    assert envelope.prompt == "helloworld"
