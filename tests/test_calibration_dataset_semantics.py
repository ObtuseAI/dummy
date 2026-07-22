from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from calibration.schema import ForecastRecordV2, SettlementRecord
from calibration.spine import CalibrationSpine


BASE = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)


def _forecast(
    market: str,
    probability: str,
    *,
    timestamp: datetime | None = None,
    category: str | None = None,
    horizon: str | None = None,
    forecast_id: str | None = None,
    realized_outcome: int | None = None,
) -> ForecastRecordV2:
    return ForecastRecordV2(
        forecast_id=forecast_id or f"forecast-{market}-{probability}",
        market_ticker=market,
        contract_ticker=f"{market}-YES",
        category=category,
        horizon=horizon,
        model_route="test-model",
        market_implied_probability=Decimal("0.50"),
        dummy_probability=Decimal(probability),
        final_probability=Decimal(probability),
        confidence_bucket="medium",
        timestamp=timestamp or BASE - timedelta(hours=12),
        realized_outcome=realized_outcome,
    )


def _settlement(
    market: str,
    outcome: int,
    *,
    settled_at: datetime | None = None,
    source: str = "read-only-truth",
) -> SettlementRecord:
    return SettlementRecord(
        market_ticker=market,
        contract_ticker=f"{market}-YES",
        outcome=outcome,
        settled_at=settled_at or BASE,
        source=source,
    )


def test_dataset_ece_and_mce_use_unique_cross_contract_points() -> None:
    forecasts = [
        _forecast("SPORT-A", "0.15", category="sports", horizon="daily"),
        _forecast("SPORT-B", "0.15", category="sports", horizon="daily"),
        _forecast("CRYPTO-A", "0.85", category="crypto", horizon="daily"),
        _forecast("CRYPTO-B", "0.85", category="crypto", horizon="daily"),
    ]
    settlements = [
        _settlement("SPORT-A", 0),
        _settlement("SPORT-B", 0),
        _settlement("CRYPTO-A", 1),
        _settlement("CRYPTO-B", 0),
    ]

    scored = CalibrationSpine().score_dataset_v2(forecasts, settlements)
    overall = scored["overall"]

    assert scored["calibration_unit"] == "unique_market_contract"
    assert overall["sample_size"] == 4
    assert overall["sample_quality"] == "LOW_SAMPLE"
    assert overall["brier_score"] == pytest.approx(0.1975)
    assert overall["expected_calibration_error"] == pytest.approx(0.25)
    assert overall["maximum_calibration_error"] == pytest.approx(0.35)
    assert overall["brier_score_ci_95"] is not None
    assert scored["domain_slices"]["sports"][
        "expected_calibration_error"
    ] == pytest.approx(0.15)
    assert scored["domain_slices"]["crypto"][
        "maximum_calibration_error"
    ] == pytest.approx(0.35)
    assert scored["horizon_slices"]["daily"]["sample_size"] == 4
    assert scored["temporal_slices"]["2026-01"]["sample_size"] == 4
    assert scored["forecast_temporal_slices"]["2026-01"]["sample_size"] == 4
    assert scored["domain_horizon_slices"]["sports"]["daily"]["sample_size"] == 2


def test_dataset_selects_latest_pre_settlement_and_excludes_future_rows() -> None:
    forecasts = [
        _forecast(
            "MKT-A",
            "0.10",
            timestamp=BASE - timedelta(hours=2),
            forecast_id="a-old",
        ),
        _forecast(
            "MKT-A",
            "0.80",
            timestamp=BASE - timedelta(minutes=5),
            forecast_id="a-latest",
        ),
        _forecast(
            "MKT-A",
            "0.99",
            timestamp=BASE + timedelta(seconds=1),
            forecast_id="a-future",
        ),
        _forecast("MKT-B", "0.20", forecast_id="b-only"),
    ]
    settlements = [
        _settlement("MKT-A", 1),
        _settlement("MKT-A", 1, source="retry-source"),
        _settlement("MKT-B", 0),
    ]

    scored = CalibrationSpine().score_dataset_v2(forecasts, settlements)
    by_market = {row["market_ticker"]: row for row in scored["contract_metrics"]}

    assert scored["overall"]["sample_size"] == 2
    assert by_market["MKT-A"]["forecast_id"] == "a-latest"
    assert by_market["MKT-A"]["brier_score"] == pytest.approx(0.04)
    assert scored["diagnostics"]["duplicate_settlement_count"] == 1
    assert scored["diagnostics"]["post_settlement_forecast_count"] == 1
    assert scored["diagnostics"]["superseded_pre_settlement_forecast_count"] == 1


def test_dataset_conflicting_settlement_truth_is_excluded_fail_closed() -> None:
    forecasts = [
        _forecast("CONFLICT", "0.75"),
        _forecast("VALID", "0.25"),
    ]
    settlements = [
        _settlement("CONFLICT", 1),
        _settlement("CONFLICT", 0),
        _settlement("VALID", 0),
    ]

    scored = CalibrationSpine().score_dataset_v2(forecasts, settlements)

    assert scored["overall"]["sample_size"] == 1
    assert scored["overall"]["status"] == "INSUFFICIENT_DATA"
    assert scored["overall"]["expected_calibration_error"] is None
    assert scored["overall"]["maximum_calibration_error"] is None
    assert scored["diagnostics"]["conflicting_settlement_contract_count"] == 1
    assert [row["market_ticker"] for row in scored["contract_metrics"]] == ["VALID"]


def test_dataset_rejects_naive_timestamps_as_point_in_time_evidence() -> None:
    naive = datetime(2026, 1, 10, 10)
    forecasts = [
        _forecast("NAIVE", "0.60", timestamp=naive),
        _forecast("VALID", "0.40"),
    ]

    scored = CalibrationSpine().score_dataset_v2(
        forecasts,
        [_settlement("NAIVE", 1), _settlement("VALID", 0)],
    )

    assert scored["overall"]["sample_size"] == 1
    assert scored["diagnostics"]["invalid_forecast_timestamp_count"] == 1
    assert scored["diagnostics"]["unmatched_settlement_count"] == 1


def test_dataset_rejects_at_settlement_forecast_as_outcome_leakage() -> None:
    forecasts = [
        _forecast(
            "AT-SETTLEMENT",
            "1.0",
            timestamp=BASE,
            realized_outcome=1,
        ),
        _forecast("VALID", "0.40"),
    ]

    scored = CalibrationSpine().score_dataset_v2(
        forecasts,
        [_settlement("AT-SETTLEMENT", 1), _settlement("VALID", 0)],
    )

    assert scored["overall"]["sample_size"] == 1
    assert scored["diagnostics"]["at_settlement_forecast_count"] == 1
    assert scored["diagnostics"]["unmatched_settlement_count"] == 1
    assert [row["market_ticker"] for row in scored["contract_metrics"]] == ["VALID"]


def test_market_skill_uses_only_contracts_with_valid_paired_market_prices() -> None:
    forecasts = [
        _forecast("PAIRED", "0.10", forecast_id="paired"),
        ForecastRecordV2(
            **{
                **_forecast("NO-MARKET", "0.10", forecast_id="unpaired").model_dump(),
                "market_implied_probability": Decimal("1.5"),
            }
        ),
    ]
    settlements = [_settlement("PAIRED", 0), _settlement("NO-MARKET", 1)]

    scored = CalibrationSpine().score_dataset_v2(forecasts, settlements)

    assert scored["overall"]["brier_score"] == pytest.approx(0.41)
    assert scored["overall"]["market_sample_count"] == 1
    assert scored["overall"]["market_brier_score"] == pytest.approx(0.25)
    assert scored["overall"]["paired_forecast_brier_score"] == pytest.approx(0.01)
    assert scored["overall"]["brier_skill_vs_market"] == pytest.approx(0.24)


def test_empty_settlement_source_is_not_truth_authority() -> None:
    scored = CalibrationSpine().score_dataset_v2(
        [_forecast("NO-SOURCE", "0.80")],
        [_settlement("NO-SOURCE", 1, source="")],
    )

    assert scored["overall"]["sample_size"] == 0
    assert scored["diagnostics"]["invalid_settlement_count"] == 1
