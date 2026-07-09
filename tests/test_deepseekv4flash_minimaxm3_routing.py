import pytest

from model_router.router import ModelRouter
from model_router.tasks import ModelTask


@pytest.mark.asyncio
async def test_deepseekv4flash_route_when_key_present(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-routing-test")
    router = ModelRouter()
    decision = router.route(ModelTask.FORECAST_OPINION)
    assert decision.provider_name == "deepseek_v4_flash"
    assert decision.model_name == "deepseek/deepseek-chat"


@pytest.mark.asyncio
async def test_minimaxm3_route_when_key_present(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-routing-test")
    router = ModelRouter()
    decision = router.route(ModelTask.STRATEGY_CRITIQUE)
    assert decision.provider_name == "minimax_m3"
    assert decision.model_name == "minimax/minimax-01"


@pytest.mark.asyncio
async def test_deepseekv4flash_minimaxm3_mock_fallback_when_keys_absent(monkeypatch, no_project_env):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    router = ModelRouter()
    assert router.route(ModelTask.FORECAST_OPINION).provider_name == "mock"
    assert router.route(ModelTask.MARKET_THESIS).provider_name == "mock"
