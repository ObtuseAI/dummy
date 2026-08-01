"""LLM routing: exact four-voice OpenRouter panel.

Fast structured work routes to Terra/Luna, deep synthesis to Claude, and
adversarial calibration to GLM. Legacy providers remain fallback-only.
"""
import pytest

from model_router.router import ModelRouter
from model_router.tasks import ModelTask


@pytest.mark.asyncio
async def test_terra_routes_primary_forecast_when_key_present(monkeypatch):
    monkeypatch.setenv("DUMMY_LLM_OPENROUTER_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-routing-test")
    router = ModelRouter()
    decision = router.route(ModelTask.FORECAST_OPINION)
    assert decision.provider_name == "gpt_5_6_terra"
    assert decision.model_name == "openai/gpt-5.6-terra"


@pytest.mark.asyncio
async def test_luna_routes_rapid_forecasts_and_drafts_when_key_present(monkeypatch):
    monkeypatch.setenv("DUMMY_LLM_OPENROUTER_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-routing-test")
    router = ModelRouter()
    for task in (ModelTask.RAPID_FORECAST, ModelTask.TRADE_DRAFT):
        decision = router.route(task)
        assert decision.provider_name == "gpt_5_6_luna"
        assert decision.model_name == "openai/gpt-5.6-luna"


@pytest.mark.asyncio
async def test_claude_routes_deep_strategy_and_synthesis_when_key_present(monkeypatch):
    monkeypatch.setenv("DUMMY_LLM_OPENROUTER_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-routing-test")
    router = ModelRouter()
    for task in (ModelTask.STRATEGY_CRITIQUE, ModelTask.MARKET_THESIS):
        decision = router.route(task)
        assert decision.provider_name == "claude_sonnet_5"
        assert decision.model_name == "anthropic/claude-sonnet-5"


@pytest.mark.asyncio
async def test_glm_routes_adversarial_risk_no_trade_and_calibration_when_key_present(monkeypatch):
    monkeypatch.setenv("DUMMY_LLM_OPENROUTER_ENABLED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-routing-test")
    router = ModelRouter()
    for task in (
        ModelTask.RISK_CRITIQUE,
        ModelTask.NO_TRADE_REASON,
        ModelTask.CALIBRATION_NOTE,
    ):
        decision = router.route(task)
        assert decision.provider_name == "glm_5_2"
        assert decision.model_name == "z-ai/glm-5.2"


@pytest.mark.asyncio
async def test_mock_fallback_when_keys_absent(monkeypatch, no_project_env):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    router = ModelRouter()
    assert router.route(ModelTask.FORECAST_OPINION).provider_name == "mock"
    assert router.route(ModelTask.MARKET_THESIS).provider_name == "mock"
