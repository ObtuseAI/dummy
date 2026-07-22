from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import autonomy.crypto_horizon_evidence as horizon_evidence
from autonomy.crypto_horizon_evidence import (
    CryptoHorizonEvidenceMatrix,
    CryptoHorizonEvidenceStore,
    PointInTimeViolation,
    deterministic_provenance_hash,
    expanding_window_calibration,
    validate_point_in_time,
)
from autonomy.ontology import MarketView, Signal, Vertical


AS_OF = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)


def _state(offset_seconds: int = -60) -> dict:
    stamp = int((AS_OF + timedelta(seconds=offset_seconds)).timestamp())
    candle = {
        "at_s": stamp, "low": 99_900.0, "high": 100_100.0,
        "open": 99_950.0, "close": 100_000.0, "volume": 11.0,
    }
    return {
        "asset": "BTC", "spot": 100_000.0, "coinbase_spot": 100_000.0,
        "kraken_spot": 100_010.0, "hourly_source": "coinbase",
        "hourly_closes": [99_000.0, 100_000.0],
        "daily_closes": [95_000.0, 100_000.0],
        "minute_closes": [99_900.0, 100_000.0], "minute_volumes": [10.0, 11.0],
        "minute_ohlcv": [candle], "hourly_ohlcv": [], "daily_ohlcv": [],
        "coinbase_hourly_at_s": stamp, "coinbase_minute_at_s": stamp,
        "dvol": 55.0, "dvol_at_ms": stamp * 1000,
        "book_imbalance": 0.1, "microprice_basis_bps": 0.2,
    }


def _market(*, fetched_at: datetime | None = None) -> MarketView:
    return MarketView(
        ticker="KXBTC15M-21JUL261215-15", title="BTC direction",
        vertical=Vertical.CRYPTO, status="open",
        close_time=(AS_OF + timedelta(minutes=15)).isoformat(),
        yes_bid=45, yes_ask=47, no_bid=53, no_ask=55,
        volume=500, liquidity=10_000,
        raw={"open_time": AS_OF.isoformat(), "strike_type": "greater",
             "floor_strike": 100_000},
        fetched_at=(fetched_at or AS_OF - timedelta(seconds=5)).isoformat(),
    )


class _Source:
    name = "pit_fixture"

    def applicable(self, market: MarketView) -> bool:
        return True

    def generate(self, market: MarketView) -> Signal:
        return Signal(
            source=self.name, market_ticker=market.ticker,
            probability_yes=0.7, uncertainty=0.2, rationale="fixture",
            features={"challenger_only": True},
            created_at=(AS_OF - timedelta(seconds=1)).isoformat(),
        )


def test_provenance_hash_is_order_independent() -> None:
    left = {"source": "coinbase", "nested": {"b": 2, "a": [1, 2]},
            "observed_at": AS_OF}
    right = {"observed_at": AS_OF, "nested": {"a": [1, 2], "b": 2},
             "source": "coinbase"}
    assert deterministic_provenance_hash(left) == deterministic_provenance_hash(right)
    assert deterministic_provenance_hash(left) != deterministic_provenance_hash(
        {**right, "source": "kraken"}
    )


def test_point_in_time_rejects_future_market_and_source() -> None:
    validate_point_in_time(_market(), _state(), AS_OF)
    with pytest.raises(PointInTimeViolation, match="future source observation"):
        validate_point_in_time(_market(), _state(1), AS_OF)
    with pytest.raises(PointInTimeViolation, match="fetched after as_of"):
        validate_point_in_time(
            _market(fetched_at=AS_OF + timedelta(seconds=1)), _state(), AS_OF
        )


def test_matrix_quarantines_future_state_without_scoring(tmp_path) -> None:
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    matrix = CryptoHorizonEvidenceMatrix(
        store=store, sources=[_Source()], now_fn=lambda: AS_OF
    )
    try:
        report = matrix.run_cycle([_market()], states={"BTC": _state(1)}, as_of=AS_OF)
        assert report["received_at"] == AS_OF.isoformat()
        attempts = store.attempts(cycle_id=report["cycle_id"])
        assert len(attempts) == 1
        assert attempts[0]["status"] == "PIT_REJECTED"
        assert attempts[0]["probability_yes"] is None
        assert report["settled_evidence"]["settled_forecasts"] == 0
    finally:
        matrix.close()


def _settled_row(
    forecast_id: str,
    decision_at: datetime | str,
    settled_at: datetime | str | None,
) -> dict:
    return {
        "forecast_id": forecast_id,
        "as_of_at": (
            decision_at.isoformat() if isinstance(decision_at, datetime) else decision_at
        ),
        "settled_at": (
            settled_at.isoformat() if isinstance(settled_at, datetime) else settled_at
        ),
        "probability_yes": 0.7,
        "market_probability": 0.5,
        "result_yes": 1,
        "event_cluster": f"cluster-{forecast_id}",
    }


def test_expanding_calibration_waits_for_outcome_release_not_forecast_order(
    monkeypatch,
) -> None:
    t0 = AS_OF
    rows = [
        _settled_row("late", t0, t0 + timedelta(hours=4)),
        _settled_row(
            "released", t0 + timedelta(hours=1), t0 + timedelta(hours=2)
        ),
        _settled_row("test", t0 + timedelta(hours=3), t0 + timedelta(hours=5)),
    ]
    fitted_ids: list[list[str]] = []

    def capture_fit(training_rows) -> float:
        fitted_ids.append([str(row["forecast_id"]) for row in training_rows])
        return 0.0

    monkeypatch.setattr(horizon_evidence, "_fit_market_blend", capture_fit)
    report = expanding_window_calibration(rows, min_train=1, min_forward=1)

    # The forecast created first is still unresolved at the test decision. It
    # must not train that decision; only the outcome released at hour 2 may.
    assert fitted_ids[0] == ["released"]
    assert "late" not in fitted_ids[0]
    assert report["forward_forecasts"] == 1
    audit = report["point_in_time_training"]
    assert audit["release_rule"] == "settled_at_strictly_before_test_as_of_at"
    assert audit["training_rows_min"] == 1
    assert audit["training_rows_max"] == 1
    assert audit["earlier_forecast_rows_with_outcomes_unreleased_at_test_decision"] == 2


def test_expanding_calibration_blocks_same_cycle_and_unknown_timestamps(
    monkeypatch,
) -> None:
    t0 = AS_OF
    rows = [
        _settled_row("released", t0, t0 + timedelta(hours=1)),
        _settled_row(
            "equal-boundary",
            t0 + timedelta(minutes=30),
            t0 + timedelta(hours=2),
        ),
        _settled_row("same-a", t0 + timedelta(hours=2), t0 + timedelta(hours=3)),
        _settled_row("same-b", t0 + timedelta(hours=2), t0 + timedelta(hours=3)),
        _settled_row("missing-settlement", t0 - timedelta(hours=1), None),
        _settled_row(
            "naive-decision", "2026-07-21T10:00:00", t0 + timedelta(hours=4)
        ),
    ]
    fitted_ids: list[list[str]] = []

    def capture_fit(training_rows) -> float:
        fitted_ids.append([str(row["forecast_id"]) for row in training_rows])
        return 0.0

    monkeypatch.setattr(horizon_evidence, "_fit_market_blend", capture_fit)
    report = expanding_window_calibration(rows, min_train=1, min_forward=1)

    # Both forecasts in the hour-2 decision batch see exactly the same frozen
    # history. A settlement at the hour-2 boundary is not "strictly before."
    assert fitted_ids[:2] == [["released"], ["released"]]
    assert report["forward_forecasts"] == 2
    audit = report["point_in_time_training"]
    assert audit["same_decision_batch_can_train_each_other"] is False
    assert audit["timestamp_valid_rows"] == 4
    assert audit["timestamp_excluded_rows"] == 2
    assert audit["timestamp_exclusion_reasons"] == {
        "invalid_decision_timestamp": 1,
        "missing_settlement_timestamp": 1,
    }
