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
async def test_forecast_opinion_manifest_v2_schema(no_creds, tmp_path):
    artifact_dir = tmp_path / "artifacts" / "dummy"
    storage = CalibrationStorage(data_dir=tmp_path / "calibration")
    loop = RealMarketForecastLoopV2(artifact_dir=artifact_dir, storage=storage)
    run_result = await loop.run(max_markets=4)

    manifest_path = artifact_dir / "forecast_opinion_manifest_v2.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())

    assert manifest["manifest_type"] == "forecast_opinion_manifest_v2"
    assert manifest["model_mode"] == "MOCK_ONLY"
    assert manifest["source"] == "mock"
    assert manifest["opinion_count"] == run_result["count"]
    assert len(manifest["opinions"]) == run_result["count"]

    required_fields = set(ForecastOpinion.model_fields.keys())
    for opinion in manifest["opinions"]:
        assert required_fields.issubset(set(opinion.keys()))
        ForecastOpinion.model_validate(opinion)
        assert 0 <= float(opinion["confidence_score"]) <= 1
        assert 0 <= float(opinion["dummy_probability"]) <= 1
        assert 0 <= float(opinion["market_implied_probability"]) <= 1
