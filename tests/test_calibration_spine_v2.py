import json
from datetime import datetime, timezone
from decimal import Decimal
from math import log
from pathlib import Path

import pytest

from calibration.schema import ForecastRecordV2, SettlementRecord
from calibration.spine import CalibrationSpine


@pytest.fixture
def artifact_dir():
    path = Path("artifacts/dummy")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _record(
    final_probability: str,
    market_implied: str = "0.5",
    dummy: str = "0.5",
    deepseek: str | None = None,
    minimax: str | None = None,
    bucket: str = "medium",
    no_trade: str | None = None,
    status: str = "settled",
    outcome: int | None = 1,
):
    return ForecastRecordV2(
        forecast_id=f"fc_{final_probability}_{bucket}",
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        model_route="deepseek_v4_flash+minimax_m3",
        market_implied_probability=Decimal(market_implied),
        dummy_probability=Decimal(dummy),
        deepseekv4flash_probability=Decimal(deepseek) if deepseek is not None else None,
        minimaxm3_probability=Decimal(minimax) if minimax is not None else None,
        final_probability=Decimal(final_probability),
        confidence_bucket=bucket,
        timestamp=datetime.now(timezone.utc),
        settlement_status=status,
        realized_outcome=outcome,
        no_trade_reason=no_trade,
    )


def test_score_v2_perfect_forecast():
    spine = CalibrationSpine()
    fc = _record("1.0", deepseek="0.95", minimax="0.98")
    settlement = SettlementRecord(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        outcome=1,
        settled_at=datetime.now(timezone.utc),
        source="test",
    )
    metrics = spine.score_v2([fc], settlement)
    assert metrics.brier_score == 0.0
    assert metrics.log_loss == pytest.approx(0.0, abs=1e-6)
    assert metrics.sample_count == 1
    assert metrics.settled_count == 1
    assert metrics.expected_calibration_error is None


def test_score_v2_wrong_forecast():
    spine = CalibrationSpine()
    fc = _record("0.0", deepseek="0.05", minimax="0.02")
    settlement = SettlementRecord(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        outcome=1,
        settled_at=datetime.now(timezone.utc),
        source="test",
    )
    metrics = spine.score_v2([fc], settlement)
    assert metrics.brier_score == 1.0
    assert metrics.log_loss == pytest.approx(-log(1e-9), abs=1e-3)


def test_score_v2_multi_model_disagreement():
    spine = CalibrationSpine()
    fcs = [
        _record("0.8", market_implied="0.5", dummy="0.75", deepseek="0.85", minimax="0.80"),
        _record("0.2", market_implied="0.5", dummy="0.25", deepseek="0.15", minimax="0.20"),
    ]
    settlement = SettlementRecord(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        outcome=1,
        settled_at=datetime.now(timezone.utc),
        source="test",
    )
    metrics = spine.score_v2(fcs, settlement)
    assert metrics.brier_score == pytest.approx(0.34, abs=0.01)
    assert metrics.model_disagreement_score is not None
    assert metrics.model_disagreement_score > 0.0
    assert metrics.market_implied_delta == pytest.approx(0.3, abs=0.01)


def test_score_v2_abstention_tracking():
    spine = CalibrationSpine()
    fcs = [
        _record("0.6", bucket="medium"),
        _record("0.6", bucket="medium", no_trade="confidence below threshold"),
        _record("0.6", bucket="medium", no_trade="insufficient liquidity"),
    ]
    settlement = SettlementRecord(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        outcome=1,
        settled_at=datetime.now(timezone.utc),
        source="test",
    )
    metrics = spine.score_v2(fcs, settlement)
    assert metrics.abstention_count == 2
    assert metrics.abstention_rate == pytest.approx(2 / 3, abs=1e-6)
    assert "confidence below threshold" in metrics.no_trade_reasons
    assert "insufficient liquidity" in metrics.no_trade_reasons


def test_score_v2_empty_forecasts():
    spine = CalibrationSpine()
    settlement = SettlementRecord(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        outcome=0,
        settled_at=datetime.now(timezone.utc),
        source="test",
    )
    metrics = spine.score_v2([], settlement)
    assert metrics.sample_count == 0
    assert metrics.brier_score is None
    assert metrics.expected_calibration_error is None


def test_score_v2_confidence_bucket_accuracy(artifact_dir):
    spine = CalibrationSpine()
    fcs = [
        _record("0.85", bucket="high"),
        _record("0.75", bucket="high"),
        _record("0.55", bucket="medium"),
        _record("0.25", bucket="low"),
    ]
    settlement = SettlementRecord(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        outcome=1,
        settled_at=datetime.now(timezone.utc),
        source="test",
    )
    metrics = spine.score_v2(fcs, settlement)
    assert metrics.confidence_bucket_accuracy["high"] == 1.0
    assert metrics.confidence_bucket_accuracy["medium"] == 1.0
    assert metrics.confidence_bucket_accuracy["low"] == 0.0

    report_path = artifact_dir / "calibration_spine_report_v2.json"
    report = {
        "report_type": "calibration_spine_v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_ticker": "MKT",
        "contract_ticker": "MKT-YES",
        "metrics": metrics.model_dump(mode="json"),
    }
    report_path.write_text(json.dumps(report, indent=2))
    assert report_path.exists()
