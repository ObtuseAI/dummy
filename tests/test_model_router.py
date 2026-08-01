from __future__ import annotations


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
async def test_hybrid_review_resolves_to_terra_when_available(monkeypatch):
    monkeypatch.setenv("DUMMY_LLM_OPENROUTER_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-test")
    router = ModelRouter()
    decision = router.route(ModelTask.HYBRID_REVIEW)
    assert decision.provider_name == "gpt_5_6_terra"
    assert decision.model_name == "openai/gpt-5.6-terra"
    assert router.hybrid_provider_names() == [
        "gpt_5_6_terra",
        "gpt_5_6_luna",
        "claude_sonnet_5",
        "glm_5_2",
    ]


@pytest.mark.asyncio
async def test_hybrid_review_fallback_when_terra_unavailable(monkeypatch, no_project_env):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    router = ModelRouter()
    decision = router.route(ModelTask.HYBRID_REVIEW)
    assert decision.provider_name == "mock"
    assert decision.fallback_reason == "gpt_5_6_terra_credentials_missing"


@pytest.mark.asyncio
async def test_preferred_provider_used_when_key_present(monkeypatch):
    monkeypatch.setenv("DUMMY_LLM_OPENROUTER_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-test")
    router = ModelRouter()

    expected_routes = {
        ModelTask.FORECAST_OPINION: "gpt_5_6_terra",
        ModelTask.RAPID_FORECAST: "gpt_5_6_luna",
        ModelTask.TRADE_DRAFT: "gpt_5_6_luna",
        ModelTask.STRATEGY_CRITIQUE: "claude_sonnet_5",
        ModelTask.MARKET_THESIS: "claude_sonnet_5",
        ModelTask.RISK_CRITIQUE: "glm_5_2",
        ModelTask.NO_TRADE_REASON: "glm_5_2",
        ModelTask.CALIBRATION_NOTE: "glm_5_2",
    }
    for task, provider_name in expected_routes.items():
        assert router.route(task).provider_name == provider_name


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
