"""LLM routing: GLM-5.2 + MiniMax-M3 hybrid (operator directive 2026-07-17).

Every role routes to one of the two directed models (or the hybrid panel);
deepseek remains configured only as a fallback alias target.
"""
import pytest

from model_router.router import ModelRouter
from model_router.tasks import ModelTask


@pytest.mark.asyncio
async def test_glm52_routes_thesis_and_drafts_when_key_present(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-routing-test")
    router = ModelRouter()
    for task in (ModelTask.FORECAST_OPINION, ModelTask.TRADE_DRAFT, ModelTask.MARKET_THESIS):
        decision = router.route(task)
        assert decision.provider_name == "glm_5_2"
        assert decision.model_name == "z-ai/glm-5.2"


@pytest.mark.asyncio
async def test_minimaxm3_routes_critiques_when_key_present(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-routing-test")
    router = ModelRouter()
    for task in (
        ModelTask.STRATEGY_CRITIQUE,
        ModelTask.RISK_CRITIQUE,
        ModelTask.NO_TRADE_REASON,
        ModelTask.CALIBRATION_NOTE,
    ):
        decision = router.route(task)
        assert decision.provider_name == "minimax_m3"
        assert decision.model_name == "minimax/minimax-m3"


@pytest.mark.asyncio
async def test_mock_fallback_when_keys_absent(monkeypatch, no_project_env):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    router = ModelRouter()
    assert router.route(ModelTask.FORECAST_OPINION).provider_name == "mock"
    assert router.route(ModelTask.MARKET_THESIS).provider_name == "mock"
