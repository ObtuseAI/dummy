import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import pytest

from calibration.storage import CalibrationStorage
from core.ontology import Contract, ForecastOpinion, Market, OrderBook, OrderBookLevel
from forecasting.real_market_loop import REVIEW_ROUTE_CONTRACTS, RealMarketForecastLoopV2
from model_router.config import ModelRoutingConfig, ProviderConfig
from model_router.envelope import ModelResponseEnvelope, ModelRouteDecision


@pytest.fixture
def no_creds(monkeypatch):
    for name in (
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "DEEPSEEK_API_KEY",
        "MINIMAX_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def _routing_config(*, live_enabled: bool = True) -> ModelRoutingConfig:
    return ModelRoutingConfig(
        default_provider={
            **{
                task.value: provider_name
                for task, provider_name, _model_name in REVIEW_ROUTE_CONTRACTS.values()
            },
            "trade_draft": "gpt_5_6_luna",
            "hybrid_review": "hybrid",
        },
        hybrid_providers=[
            "gemini_3_6_flash",
            "gpt_5_6_luna",
            "claude_sonnet_5",
            "glm_5_2",
        ],
        provider_configs={
            "gemini_3_6_flash": ProviderConfig(
                api_base="https://openrouter.ai/api",
                api_key_env="OPENROUTER_API_KEY",
                model_name="google/gemini-3.6-flash",
                route_mode="openrouter",
            ),
            "gpt_5_6_luna": ProviderConfig(
                api_base="https://openrouter.ai/api",
                api_key_env="OPENROUTER_API_KEY",
                model_name="openai/gpt-5.6-luna",
                route_mode="openrouter",
            ),
            "claude_sonnet_5": ProviderConfig(
                api_base="https://openrouter.ai/api",
                api_key_env="OPENROUTER_API_KEY",
                model_name="anthropic/claude-sonnet-5",
                route_mode="openrouter",
            ),
            "glm_5_2": ProviderConfig(
                api_base="https://openrouter.ai/api",
                api_key_env="OPENROUTER_API_KEY",
                model_name="z-ai/glm-5.2",
                route_mode="openrouter",
            ),
        },
        live_model_calls_enabled=live_enabled,
    )


def _review_payload(review_key: str) -> dict:
    if review_key == "primary_forecast":
        return {
            "dummy_probability": "0.90",
            "confidence_score": "0.90",
            "uncertainty_band": ["0.80", "0.95"],
            "reasoning": "test forecast",
            "evidence_used": ["supplied orderbook"],
        }
    if review_key == "rapid_forecast":
        return {
            "dummy_probability": "0.88",
            "confidence_score": "0.86",
            "uncertainty_band": ["0.78", "0.94"],
            "reasoning": "test rapid forecast",
            "action": "consider_yes",
            "entry_condition": "ask remains at or below 51 cents",
        }
    if review_key == "no_trade":
        return {"reason": None, "contributing_factors": []}
    if review_key == "critique":
        return {"verdict": "proceed", "reasoning": "test critique"}
    if review_key == "risk":
        return {"risk_level": "low", "reasoning": "test risk"}
    if review_key == "thesis":
        return {"thesis": "test thesis", "confidence": 0.8}
    return {"note": "test calibration note"}


def _valid_reviews() -> dict[str, ModelResponseEnvelope]:
    reviews: dict[str, ModelResponseEnvelope] = {}
    for review_key, (task, provider_name, model_name) in REVIEW_ROUTE_CONTRACTS.items():
        reviews[review_key] = ModelResponseEnvelope(
            task=task,
            decision=ModelRouteDecision(
                task=task,
                provider_name=provider_name,
                model_name=model_name,
                reason="task default provider",
            ),
            prompt="test",
            content=json.dumps(_review_payload(review_key)),
            raw_metadata={
                "provider": "openrouter_generic",
                "model": model_name,
                "error_class": None,
            },
            latency_ms=1.0,
        )
    return reviews


class _FakeHybridEngine:
    def __init__(self, *, live_enabled: bool = True, bad_call: int | None = None):
        config = _routing_config(live_enabled=live_enabled)
        self.router = SimpleNamespace(
            config=config,
            providers={
                "gemini_3_6_flash": SimpleNamespace(available=True),
                "gpt_5_6_luna": SimpleNamespace(available=True),
                "claude_sonnet_5": SimpleNamespace(available=True),
                "glm_5_2": SimpleNamespace(available=True),
            },
        )
        self.calls = 0
        self.bad_call = bad_call

    async def hybrid_review(self, **_kwargs):
        self.calls += 1
        reviews = _valid_reviews()
        if self.calls == self.bad_call:
            reviews["risk"].raw_metadata["model"] = "openai/wrong-model"
        return reviews


@pytest.mark.asyncio
async def test_v2_mock_fallback_runs_without_credentials(no_creds, tmp_path):
    artifact_dir = tmp_path / "artifacts" / "dummy"
    storage = CalibrationStorage(data_dir=tmp_path / "calibration")
    loop = RealMarketForecastLoopV2(artifact_dir=artifact_dir, storage=storage)
    result = await loop.run(max_markets=5)

    assert result["source"] == "mock"
    assert result["model_mode"] == "MOCK_ONLY"
    assert result["kalshi_credentials_present"] is False
    assert result["count"] == 4
    assert len(result["opinions"]) == 4

    for opinion in result["opinions"]:
        ForecastOpinion.model_validate(opinion)

    assert (artifact_dir / "real_market_forecast_loop_report_v2.json").exists()
    assert (artifact_dir / "forecast_opinion_manifest_v2.json").exists()
    assert (artifact_dir / "live_hybrid_forecast_proof_report_v1.json").exists()


@pytest.mark.asyncio
async def test_v2_bounded_sample_excludes_data_only_targets(no_creds, tmp_path):
    artifact_dir = tmp_path / "artifacts" / "dummy"
    storage = CalibrationStorage(data_dir=tmp_path / "calibration")
    loop = RealMarketForecastLoopV2(artifact_dir=artifact_dir, storage=storage)
    result = await loop.run(max_markets=3)

    assert result["count"] == 3
    tickers = [op["contract_ticker"] for op in result["opinions"]]
    assert "KXMLBGAME-26JUL21NYYBOS-NYY-YES" in tickers
    assert "BTC-ABOVE-100K-YES" in tickers
    assert "SPX-ABOVE-5000-YES" not in tickers
    assert "MEME-STALE-YES" in tickers
    assert not any("WEATHER" in ticker or "KXWTI" in ticker for ticker in tickers)


@pytest.mark.asyncio
async def test_v2_opinions_marked_mock_only_when_credentials_absent(no_creds, tmp_path):
    artifact_dir = tmp_path / "artifacts" / "dummy"
    storage = CalibrationStorage(data_dir=tmp_path / "calibration")
    loop = RealMarketForecastLoopV2(artifact_dir=artifact_dir, storage=storage)
    result = await loop.run(max_markets=2)

    for opinion in result["opinions"]:
        assert opinion["model_summary"].startswith("MOCK_ONLY(")
        assert opinion["no_trade_reason"] == "mock mode - simulated opinions; trading disabled"

    assert len({opinion["dummy_probability"] for opinion in result["opinions"]}) > 1


def test_v2_rejects_empty_and_crossed_books(tmp_path):
    loop = RealMarketForecastLoopV2(artifact_dir=tmp_path)
    now = datetime.now(timezone.utc)
    contract = Contract(
        ticker="M-YES",
        title="Yes",
        status="active",
        expiration=now + timedelta(hours=1),
    )
    market = Market(
        ticker="M",
        title="Market",
        status="active",
        category="Test",
        event_ticker="M",
        contracts=[contract],
    )
    empty = OrderBook(market_ticker="M", contract_ticker="M-YES", bids=[], asks=[], timestamp=now)
    crossed = OrderBook(
        market_ticker="M",
        contract_ticker="M-YES",
        bids=[OrderBookLevel(price=52, size=10)],
        asks=[OrderBookLevel(price=51, size=10)],
        timestamp=now,
    )
    assert loop._score_market(market, contract, empty) is None
    assert loop._score_market(market, contract, crossed) is None


def test_v2_uncertainty_band_validation_falls_back(tmp_path):
    loop = RealMarketForecastLoopV2(artifact_dir=tmp_path)
    fallback = loop._safe_uncertainty_band([Decimal("0.8"), Decimal("0.2")], Decimal("0.5"), Decimal("0.1"))
    assert fallback == (Decimal("0.4000"), Decimal("0.6000"))
    valid = loop._safe_uncertainty_band(["0.4", "0.7"], Decimal("0.5"), Decimal("0.1"))
    assert valid == (Decimal("0.4000"), Decimal("0.7000"))


def test_v2_stat_model_fusion_blends_and_records_disagreement(tmp_path):
    loop = RealMarketForecastLoopV2(artifact_dir=tmp_path)
    fused, clamped, disagreement = loop._fuse_probabilities(
        market_probability=Decimal("0.50"),
        statistical_probability=Decimal("0.55"),
        model_probability=Decimal("0.65"),
        statistical_weight=Decimal("0.65"),
        model_weight=Decimal("0.35"),
    )
    assert clamped == Decimal("0.6500")
    assert fused == Decimal("0.5850")
    assert disagreement == Decimal("0.1000")
    assert loop._disagreement_confidence_adjustment(disagreement) == Decimal("-0.0500")


def test_v2_fusion_helper_defaults_to_zero_model_authority(tmp_path):
    loop = RealMarketForecastLoopV2(artifact_dir=tmp_path)
    fused, _clamped, disagreement = loop._fuse_probabilities(
        market_probability=Decimal("0.50"),
        statistical_probability=Decimal("0.55"),
        model_probability=Decimal("0.65"),
    )
    assert fused == Decimal("0.5500")
    assert disagreement == Decimal("0.1000")


def test_v2_stat_model_fusion_clamps_extreme_model_probability(tmp_path):
    loop = RealMarketForecastLoopV2(artifact_dir=tmp_path)
    fused, clamped, disagreement = loop._fuse_probabilities(
        market_probability=Decimal("0.40"),
        statistical_probability=Decimal("0.45"),
        model_probability=Decimal("0.95"),
        statistical_weight=Decimal("0.65"),
        model_weight=Decimal("0.35"),
    )
    assert clamped == Decimal("0.5500")
    assert fused == Decimal("0.4850")
    assert disagreement == Decimal("0.1000")


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
    assert len(report["markets"]) == 4

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
