import json
from datetime import datetime, timezone
from decimal import Decimal

from calibration.schema import (
    CalibrationMetrics,
    CalibrationMetricsV2,
    ForecastRecord,
    ForecastRecordV2,
    SettlementRecord,
)


def test_v1_models_unchanged():
    """Ensure V1 schema compatibility is preserved."""
    fc = ForecastRecord(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        dummy_probability=Decimal("0.55"),
        confidence_score=Decimal("0.7"),
        uncertainty_band=(Decimal("0.45"), Decimal("0.65")),
        timestamp=datetime.now(timezone.utc),
        proof_reference="p1",
    )
    metrics = CalibrationMetrics(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        brier_score=0.0,
        log_loss=0.0,
        sample_count=1,
    )
    assert fc.proof_reference == "p1"
    assert metrics.sample_count == 1


def test_v2_forecast_record_required_fields():
    record = ForecastRecordV2(
        forecast_id="fc_1",
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        model_route="deepseek_v4_flash+minimax_m3",
        market_implied_probability=Decimal("0.5"),
        dummy_probability=Decimal("0.55"),
        deepseekv4flash_probability=Decimal("0.57"),
        minimaxm3_probability=Decimal("0.53"),
        final_probability=Decimal("0.55"),
        confidence_bucket="medium",
        timestamp=datetime.now(timezone.utc),
        settlement_status="settled",
        realized_outcome=1,
    )
    assert record.settlement_status == "settled"
    assert record.realized_outcome == 1
    probs = record.model_probabilities()
    assert len(probs) == 3


def test_v2_metrics_fields():
    metrics = CalibrationMetricsV2(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        brier_score=0.05,
        log_loss=0.15,
        expected_calibration_error=0.08,
        market_implied_delta=0.05,
        model_disagreement_score=0.02,
        confidence_bucket_accuracy={"high": 1.0, "medium": 0.5, "low": 0.0},
        abstention_count=2,
        abstention_rate=0.25,
        no_trade_reasons={"insufficient liquidity": 2},
        sample_count=8,
        settled_count=8,
    )
    assert metrics.expected_calibration_error == 0.08
    assert metrics.no_trade_reasons["insufficient liquidity"] == 2


def test_v2_record_defaults_to_open():
    record = ForecastRecordV2(
        forecast_id="fc_open",
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        model_route="MOCK_ONLY",
        market_implied_probability=Decimal("0.5"),
        dummy_probability=Decimal("0.55"),
        final_probability=Decimal("0.55"),
        confidence_bucket="medium",
        timestamp=datetime.now(timezone.utc),
    )
    assert record.settlement_status == "open"
    assert record.realized_outcome is None


def test_v2_schema_round_trip_json():
    record = ForecastRecordV2(
        forecast_id="fc_rt",
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        model_route="MOCK_ONLY",
        market_implied_probability=Decimal("0.5"),
        dummy_probability=Decimal("0.55"),
        final_probability=Decimal("0.55"),
        confidence_bucket="medium",
        timestamp=datetime.now(timezone.utc),
        no_trade_reason="stale market data",
    )
    payload = record.model_dump_json()
    restored = ForecastRecordV2.model_validate_json(payload)
    assert restored.forecast_id == record.forecast_id
    assert restored.no_trade_reason == record.no_trade_reason


def test_forecast_metric_schema_report_v2(tmp_path):
    # Was Path("artifacts/dummy"): a relative path resolved against the repo
    # root, so this test wrote into the REAL governance evidence tree.
    artifact_dir = tmp_path / "artifacts" / "dummy"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    record = ForecastRecordV2(
        forecast_id="fc_report",
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        model_route="deepseek_v4_flash+minimax_m3",
        market_implied_probability=Decimal("0.48"),
        dummy_probability=Decimal("0.55"),
        deepseekv4flash_probability=Decimal("0.58"),
        minimaxm3_probability=Decimal("0.52"),
        final_probability=Decimal("0.55"),
        confidence_bucket="medium",
        timestamp=datetime.now(timezone.utc),
        settlement_status="settled",
        realized_outcome=1,
    )
    settlement = SettlementRecord(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        outcome=1,
        settled_at=datetime.now(timezone.utc),
        source="test",
    )
    metrics = CalibrationMetricsV2(
        market_ticker="MKT",
        contract_ticker="MKT-YES",
        brier_score=0.2025,
        log_loss=0.5978,
        expected_calibration_error=0.05,
        market_implied_delta=0.07,
        model_disagreement_score=0.026,
        confidence_bucket_accuracy={"high": 0.0, "medium": 1.0, "low": 0.0},
        abstention_count=0,
        abstention_rate=0.0,
        no_trade_reasons={},
        sample_count=1,
        settled_count=1,
    )

    report_path = artifact_dir / "forecast_metric_schema_report_v2.json"
    report = {
        "report_type": "forecast_metric_schema_v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "v1_compatibility_preserved": True,
        "v2_forecast_record": record.model_dump(mode="json"),
        "v2_metrics": metrics.model_dump(mode="json"),
        "settlement": settlement.model_dump(mode="json"),
        "disclaimer": "Metrics are descriptive only; no profitability or SOTA performance is claimed.",
    }
    report_path.write_text(json.dumps(report, indent=2))
    assert report_path.exists()
