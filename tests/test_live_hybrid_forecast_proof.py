import json
import pytest

from calibration.storage import CalibrationStorage
from forecasting.real_market_loop import RealMarketForecastLoopV2
from forecasting.hybrid_engine import HybridForecastEngine
from model_router.tasks import ModelTask


@pytest.fixture
def no_creds(monkeypatch):
    for name in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "DEEPSEEK_API_KEY",
        "MINIMAX_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.asyncio
async def test_live_hybrid_forecast_proof_report(no_creds, tmp_path):
    artifact_dir = tmp_path / "artifacts" / "dummy"
    storage = CalibrationStorage(data_dir=tmp_path / "calibration")
    loop = RealMarketForecastLoopV2(artifact_dir=artifact_dir, storage=storage)
    result = await loop.run(max_markets=3)

    proof_path = artifact_dir / "live_hybrid_forecast_proof_report_v1.json"
    assert proof_path.exists()
    proof = json.loads(proof_path.read_text())

    assert proof["report_type"] == "live_hybrid_forecast_proof_v1"
    assert "model_mode" in proof
    assert proof["model_mode"] == "MOCK_ONLY"
    assert proof["kalshi_credentials_present"] is False
    assert proof["no_order_submitted"] is True
    assert proof["order_creating_endpoints_called"] == []
    assert proof["endpoints_called"] == []
    assert proof["opinion_count"] == result["count"]
    assert len(proof["opinion_proof_references"]) == result["count"]

    for decision in proof["model_provider_decisions"]:
        assert "deepseek_decision" in decision
        assert "critique_decision" in decision
        assert decision["deepseek_decision"]["task"] == ModelTask.FORECAST_OPINION.value
        assert decision["critique_decision"]["task"] == ModelTask.STRATEGY_CRITIQUE.value
        assert decision["risk_decision"]["task"] == ModelTask.RISK_CRITIQUE.value
        assert decision["thesis_decision"]["task"] == ModelTask.MARKET_THESIS.value


@pytest.mark.asyncio
async def test_hybrid_engine_routes_task_specific_providers(no_creds):
    engine = HybridForecastEngine()
    envelope = await engine.route_task(ModelTask.FORECAST_OPINION, "Return dummy_probability 0.5 and confidence_score 0.6")
    assert envelope.decision.provider_name == "mock"
    assert envelope.task == ModelTask.FORECAST_OPINION
    content = json.loads(envelope.content)
    assert "dummy_probability" in content
