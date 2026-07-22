from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.crypto_horizon_evidence import (
    AUTHORITY,
    CryptoHorizonEvidenceMatrix,
    CryptoHorizonEvidenceStore,
)
from autonomy.ontology import MarketView, Signal, Vertical


AS_OF = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)


def _state() -> dict:
    stamp = int((AS_OF - timedelta(minutes=1)).timestamp())
    return {
        "asset": "BTC", "spot": 100_000.0, "coinbase_spot": 100_000.0,
        "kraken_spot": 100_010.0, "hourly_source": "coinbase",
        "hourly_closes": [99_000.0, 100_000.0], "daily_closes": [],
        "minute_closes": [99_900.0, 100_000.0], "minute_volumes": [10.0, 11.0],
        "minute_ohlcv": [], "hourly_ohlcv": [], "daily_ohlcv": [],
        "coinbase_hourly_at_s": stamp, "coinbase_minute_at_s": stamp,
        "dvol": 55.0, "dvol_at_ms": stamp * 1000,
    }


def _market(ticker: str, close: datetime, opened: datetime) -> MarketView:
    return MarketView(
        ticker=ticker, title=ticker, vertical=Vertical.CRYPTO, status="open",
        close_time=close.isoformat(), yes_bid=45, yes_ask=47,
        no_bid=53, no_ask=55, volume=500, liquidity=10_000,
        raw={"open_time": opened.isoformat(), "strike_type": "greater",
             "floor_strike": 100_000},
        fetched_at=(AS_OF - timedelta(seconds=5)).isoformat(),
    )


class _Source:
    name = "settlement_fixture"

    def applicable(self, market: MarketView) -> bool:
        return True

    def generate(self, market: MarketView) -> Signal:
        probability = 0.70 if "15M" in market.ticker else 0.60
        return Signal(
            source=self.name, market_ticker=market.ticker,
            probability_yes=probability, uncertainty=0.2, rationale="fixture",
            features={"challenger_only": True},
            created_at=(AS_OF - timedelta(seconds=1)).isoformat(),
        )


def _matrix(tmp_path):
    store = CryptoHorizonEvidenceStore(tmp_path / "matrix.db")
    return store, CryptoHorizonEvidenceMatrix(
        store=store, sources=[_Source()], now_fn=lambda: AS_OF
    )


def test_settlement_is_idempotent_and_horizon_isolated(tmp_path) -> None:
    store, matrix = _matrix(tmp_path)
    short = _market(
        "KXBTC15M-21JUL261215-15", AS_OF + timedelta(minutes=15), AS_OF
    )
    daily = _market(
        "KXBTCD-22JUL26-T100000", AS_OF + timedelta(days=1), AS_OF
    )
    try:
        report = matrix.run_cycle([short, daily], states={"BTC": _state()}, as_of=AS_OF)
        assert report["attempt_statuses"] == {"EMITTED": 2}
        settled_at = AS_OF + timedelta(minutes=16)
        assert store.settle_ticker(short.ticker, True, settled_at) == 1
        assert store.settle_ticker(short.ticker, True, settled_at) == 0

        by_horizon = {row["horizon"]: row for row in store.attempts()}
        assert by_horizon["15m"]["result_yes"] == 1
        assert by_horizon["15m"]["brier"] == pytest.approx(0.09)
        assert by_horizon["1d"]["result_yes"] is None
        assert by_horizon["1d"]["brier"] is None
        rebuilt = matrix.build_report(report["cycle_id"])
        horizons = {
            scope["horizon"]
            for scope in rebuilt["settled_evidence"]["scopes"].values()
        }
        assert horizons == {"15m"}
    finally:
        matrix.close()


def test_matrix_has_no_execution_or_production_authority(tmp_path) -> None:
    store, matrix = _matrix(tmp_path)
    market = _market(
        "KXBTC15M-21JUL261215-15", AS_OF + timedelta(minutes=15), AS_OF
    )
    try:
        report = matrix.run_cycle([market], states={"BTC": _state()}, as_of=AS_OF)
        assert report["authority"] == AUTHORITY
        assert all(
            report["authority"][key] is False
            for key in (
                "execution_authority", "capital_authority",
                "production_weight_write_authority",
                "production_gate_write_authority", "production_risk_write_authority",
                "counts_toward_canary", "counts_toward_scale", "auto_promotes_sources",
            )
        )
        assert report["promotion_effect"] == "none"
        assert report["execution_effect"] == "none"
        assert report["risk_effect"] == "none"
        with sqlite3.connect(store.path) as connection:
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        assert tables == {
            "matrix_cycles", "crypto_state_snapshots", "horizon_forecast_attempts",
            "evidence_work_state",
        }
        assert not hasattr(matrix, "place_order")
        assert not hasattr(matrix, "cancel_order")
    finally:
        matrix.close()
