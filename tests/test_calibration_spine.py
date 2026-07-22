from datetime import datetime, timezone
from decimal import Decimal
from calibration.schema import ForecastRecord, SettlementRecord
from calibration.spine import CalibrationSpine


def test_perfect_forecast_brier_zero():
    spine = CalibrationSpine()
    fc = ForecastRecord(
        market_ticker="MKT", contract_ticker="MKT-YES",
        dummy_probability=Decimal("1.0"), confidence_score=Decimal("0.9"),
        uncertainty_band=(Decimal("0.9"), Decimal("1.0")),
        timestamp=datetime.now(timezone.utc), proof_reference="p1",
    )
    settlement = SettlementRecord(market_ticker="MKT", contract_ticker="MKT-YES", outcome=1, settled_at=datetime.now(timezone.utc), source="test")
    metrics = spine.score([fc], settlement)
    assert metrics.brier_score == 0.0
    assert metrics.coverage is None


def test_wrong_forecast_brier_one():
    spine = CalibrationSpine()
    fc = ForecastRecord(
        market_ticker="MKT", contract_ticker="MKT-YES",
        dummy_probability=Decimal("0.0"), confidence_score=Decimal("0.9"),
        uncertainty_band=(Decimal("0.0"), Decimal("0.1")),
        timestamp=datetime.now(timezone.utc), proof_reference="p2",
    )
    settlement = SettlementRecord(market_ticker="MKT", contract_ticker="MKT-YES", outcome=1, settled_at=datetime.now(timezone.utc), source="test")
    metrics = spine.score([fc], settlement)
    assert metrics.brier_score == 1.0
    assert metrics.coverage is None


def test_v1_score_reports_the_single_forecast_actually_scored():
    spine = CalibrationSpine()
    forecasts = [
        ForecastRecord(
            market_ticker="MKT",
            contract_ticker="MKT-YES",
            dummy_probability=Decimal(probability),
            confidence_score=Decimal("0.5"),
            uncertainty_band=(Decimal("0.1"), Decimal("0.9")),
            timestamp=datetime.now(timezone.utc),
            proof_reference=f"p-{probability}",
        )
        for probability in ("0.2", "0.8")
    ]
    settlement = SettlementRecord(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        outcome=1,
        settled_at=datetime.now(timezone.utc),
        source="test",
    )
    assert spine.score(forecasts, settlement).sample_count == 1


def test_empty_forecasts_sample_count_zero():
    spine = CalibrationSpine()
    settlement = SettlementRecord(market_ticker="MKT", contract_ticker="MKT-YES", outcome=0, settled_at=datetime.now(timezone.utc), source="test")
    metrics = spine.score([], settlement)
    assert metrics.sample_count == 0
    assert metrics.brier_score is None
