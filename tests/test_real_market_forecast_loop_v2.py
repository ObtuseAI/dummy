import json
import pytest

from calibration.storage import CalibrationStorage
from core.ontology import ForecastOpinion
from forecasting.real_market_loop import RealMarketForecastLoopV2


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
async def test_v2_mock_fallback_runs_without_credentials(no_creds, tmp_path):
    artifact_dir = tmp_path / "artifacts" / "dummy"
    storage = CalibrationStorage(data_dir=tmp_path / "calibration")
    loop = RealMarketForecastLoopV2(artifact_dir=artifact_dir, storage=storage)
    result = await loop.run(max_markets=5)

    assert result["source"] == "mock"
    assert result["model_mode"] == "MOCK_ONLY"
    assert result["kalshi_credentials_present"] is False
    assert result["count"] == 5
    assert len(result["opinions"]) == 5

    for opinion in result["opinions"]:
        ForecastOpinion.model_validate(opinion)

    assert (artifact_dir / "real_market_forecast_loop_report_v2.json").exists()
    assert (artifact_dir / "forecast_opinion_manifest_v2.json").exists()
    assert (artifact_dir / "live_hybrid_forecast_proof_report_v1.json").exists()


@pytest.mark.asyncio
async def test_v2_bounded_sample_includes_required_categories(no_creds, tmp_path):
    artifact_dir = tmp_path / "artifacts" / "dummy"
    storage = CalibrationStorage(data_dir=tmp_path / "calibration")
    loop = RealMarketForecastLoopV2(artifact_dir=artifact_dir, storage=storage)
    result = await loop.run(max_markets=3)

    assert result["count"] == 3
    tickers = [op["contract_ticker"] for op in result["opinions"]]
    assert "WEATHER-NYC-RAIN-YES" in tickers
    assert "BTC-ABOVE-100K-YES" in tickers
    assert "SPX-ABOVE-5000-YES" in tickers


@pytest.mark.asyncio
async def test_v2_opinions_marked_mock_only_when_credentials_absent(no_creds, tmp_path):
    artifact_dir = tmp_path / "artifacts" / "dummy"
    storage = CalibrationStorage(data_dir=tmp_path / "calibration")
    loop = RealMarketForecastLoopV2(artifact_dir=artifact_dir, storage=storage)
    result = await loop.run(max_markets=2)

    for opinion in result["opinions"]:
        assert opinion["model_summary"] == "MOCK_ONLY"
        assert opinion["no_trade_reason"] is not None or opinion["confidence_score"] >= 0


@pytest.mark.asyncio
async def test_v2_report_contains_quality_scores(no_creds, tmp_path):
    artifact_dir = tmp_path / "artifacts" / "dummy"
    storage = CalibrationStorage(data_dir=tmp_path / "calibration")
    loop = RealMarketForecastLoopV2(artifact_dir=artifact_dir, storage=storage)
    await loop.run(max_markets=5)

    report_path = artifact_dir / "real_market_forecast_loop_report_v2.json"
    report = json.loads(report_path.read_text())
    assert report["model_mode"] == "MOCK_ONLY"
    assert report["source"] == "mock"
    assert len(report["markets"]) == 5

    for market in report["markets"]:
        assert "market_implied_probability" in market
        assert "dummy_statistical_probability" in market
        assert "depth_score" in market
        assert "spread_score" in market
        assert "liquidity_score" in market
        assert "freshness_score" in market
        assert "settlement_risk_score" in market


@pytest.mark.asyncio
async def test_v2_does_not_submit_orders(no_creds, tmp_path):
    artifact_dir = tmp_path / "artifacts" / "dummy"
    storage = CalibrationStorage(data_dir=tmp_path / "calibration")
    loop = RealMarketForecastLoopV2(artifact_dir=artifact_dir, storage=storage)
    await loop.run(max_markets=5)

    proof_path = artifact_dir / "live_hybrid_forecast_proof_report_v1.json"
    proof = json.loads(proof_path.read_text())
    assert proof["no_order_submitted"] is True
    assert proof["order_creating_endpoints_called"] == []
    assert proof["endpoints_called"] == []
