from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core.ontology import ForecastOpinion
from strategies.disagreement import HybridDisagreementEngine, HybridDisagreementEngineV2


def _opinion(
    market_implied: Decimal = Decimal("0.50"),
    dummy: Decimal = Decimal("0.55"),
) -> ForecastOpinion:
    now = datetime.now(timezone.utc)
    return ForecastOpinion(
        market_ticker="TEST-MARKET",
        contract_ticker="TEST-CONTRACT",
        forecast_reference="forecast_ref_1",
        market_implied_probability=market_implied,
        dummy_probability=dummy,
        probability_delta=(dummy - market_implied).quantize(Decimal("0.0001")),
        confidence_score=Decimal("0.72"),
        uncertainty_band=(Decimal("0.45"), Decimal("0.65")),
        model_summary="deepseek_v4_flash+minimax_m3",
        reasoning="DeepSeek first-pass: mock | Minimax critique (proceed): mock | Risk (low): mock | Thesis: mock",
        no_trade_reason=None,
        calibration_notes=["spread_score=0.9"],
        timestamp=now,
        expiration=now,
        proof_reference="opinion_ref_1",
    )


@pytest.mark.asyncio
async def test_v1_engine_still_works():
    """V1 class must remain intact and functional."""
    engine = HybridDisagreementEngine()
    result = await engine.review(__import__("model_router.tasks", fromlist=["ModelTask"]).ModelTask.FORECAST_OPINION, "What is the probability?")
    assert "agreement_score" in result
    assert "confidence_adjustment" in result
    assert "verdict" in result
    assert "proof_reference" in result


@pytest.mark.asyncio
async def test_v2_review_returns_required_fields():
    engine = HybridDisagreementEngineV2()
    opinion = _opinion()
    result = await engine.review(
        opinion=opinion,
        strategy_signal="proceed",
        risk_governor_value="low",
        calibration_confidence=Decimal("0.80"),
    )
    assert "disagreement_score" in result
    assert "source_of_disagreement" in result
    assert "required_action" in result
    assert "no_trade_bias_adjustment" in result
    assert "proof_reference" in result
    assert "sources" in result
    assert set(result["sources"].keys()) == {
        "market_implied_probability",
        "dummy_estimate",
        "deepseek_v4_flash",
        "minimax_m3",
        "strategy_signal",
        "risk_governor",
        "calibration_confidence",
    }


@pytest.mark.asyncio
async def test_v2_low_disagreement_proceeds():
    engine = HybridDisagreementEngineV2()
    # All sources align near 0.55.
    opinion = _opinion(market_implied=Decimal("0.55"), dummy=Decimal("0.55"))
    result = await engine.review(
        opinion=opinion,
        strategy_signal={"probability": Decimal("0.55")},
        risk_governor_value={"score": Decimal("0.55")},
        calibration_confidence=Decimal("0.55"),
        context={"deepseek_probability": Decimal("0.55"), "minimax_probability": Decimal("0.55")},
    )
    assert result["disagreement_score"] <= Decimal("0.15")
    assert result["required_action"] == "PROCEED"
    assert result["no_trade_bias_adjustment"] == Decimal("0")


@pytest.mark.asyncio
async def test_v2_high_disagreement_triggers_no_trade():
    engine = HybridDisagreementEngineV2()
    # Market says 0.10, Dummy says 0.90, strategy says proceed, risk says low, calibration high.
    opinion = _opinion(market_implied=Decimal("0.10"), dummy=Decimal("0.90"))
    result = await engine.review(
        opinion=opinion,
        strategy_signal="proceed",
        risk_governor_value="low",
        calibration_confidence=Decimal("0.90"),
        context={"deepseek_probability": Decimal("0.10"), "minimax_probability": Decimal("0.90")},
    )
    assert result["disagreement_score"] > Decimal("0.30")
    assert result["required_action"] in ("REQUIRE_OPERATOR_REVIEW", "NO_TRADE")
    assert result["no_trade_bias_adjustment"] < Decimal("-0.10")


@pytest.mark.asyncio
async def test_v2_source_of_disagreement_identified():
    engine = HybridDisagreementEngineV2()
    opinion = _opinion(market_implied=Decimal("0.10"), dummy=Decimal("0.55"))
    result = await engine.review(
        opinion=opinion,
        strategy_signal="proceed",
        risk_governor_value="low",
        calibration_confidence=Decimal("0.80"),
        context={"deepseek_probability": Decimal("0.55"), "minimax_probability": Decimal("0.55")},
    )
    assert result["source_of_disagreement"] == "market_implied_probability"


@pytest.mark.asyncio
async def test_v2_normalizes_string_verdicts():
    engine = HybridDisagreementEngineV2()
    opinion = _opinion()
    result = await engine.review(
        opinion=opinion,
        strategy_signal="block",
        risk_governor_value="critical",
        calibration_confidence="0.30",
    )
    sources = result["sources"]
    assert Decimal(sources["strategy_signal"]) < Decimal("0.5")
    assert Decimal(sources["risk_governor"]) < Decimal("0.5")
    assert Decimal(sources["calibration_confidence"]) == Decimal("0.3")
