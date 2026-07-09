from datetime import datetime, timezone
from decimal import Decimal
from core.ontology import ForecastOpinion, CalibrationNote, MarketThesis


def test_forecast_opinion_defaults():
    now = datetime.now(timezone.utc)
    later = now
    opinion = ForecastOpinion(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        forecast_reference="forecast_ref_1",
        market_implied_probability=Decimal("0.5"),
        dummy_probability=Decimal("0.55"),
        probability_delta=Decimal("0.05"),
        confidence_score=Decimal("0.72"),
        uncertainty_band=(Decimal("0.5"), Decimal("0.6")),
        model_summary="hybrid_router",
        reasoning="mock forecast",
        timestamp=now,
        expiration=later,
        proof_reference="hybrid_forecast_MKT_2026-01-01T00:00:00+00:00",
    )
    assert opinion.no_trade_reason is None
    assert opinion.calibration_notes == []
    assert opinion.model_summary == "hybrid_router"


def test_calibration_note_creation():
    note = CalibrationNote(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        note="Sample calibration note",
        source="test",
        timestamp=datetime.now(timezone.utc),
    )
    assert note.source == "test"


def test_market_thesis_creation():
    thesis = MarketThesis(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        thesis="Bullish",
        bullish_signals=["signal1"],
        source="test",
        timestamp=datetime.now(timezone.utc),
    )
    assert thesis.bearish_signals == []
    assert thesis.bullish_signals == ["signal1"]
