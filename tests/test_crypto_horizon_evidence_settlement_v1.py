from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.crypto_horizon_evidence import (
    AUTHORITY,
    MIN_DISPLAY_EVENT_CLUSTERS,
    CryptoHorizonEvidenceMatrix,
    CryptoHorizonEvidenceStore,
    evidence_metrics,
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


# --------------------------------------------------------------------------
# 2026-07-24 audit §8: "headline skills of 0.90-0.99 sit on 2-11 event
# clusters, SOL-only -- noise displayed as capability; suppress skill display
# below min clusters."  The artifact must refuse to present a headline skill
# number that rests on too few independent event clusters.
# --------------------------------------------------------------------------


def _skill_rows(clusters: int) -> list[dict]:
    """Settled rows for one scope: near-perfect model, terrible market.

    One forecast per event cluster, so the cluster count IS the sample size --
    exactly the shape the audit flagged (a 0.99 skill on a handful of events).
    """
    rows: list[dict] = []
    for index in range(clusters):
        decision = AS_OF + timedelta(hours=index)
        rows.append(
            {
                "forecast_id": f"f{index}",
                "source": "crypto_technical_foundry",
                "asset": "sol",
                "horizon": "15m",
                "contract_family": "15m_direction",
                "event_cluster": f"crypto:15m:sol:{index}",
                "probability_yes": 0.99,
                "market_probability": 0.40,
                "result_yes": 1,
                "brier": 0.0001,
                "log_loss": 0.01,
                "market_brier": 0.36,
                "market_log_loss": 0.92,
                "as_of_at": decision.isoformat(),
                "settled_at": (decision + timedelta(minutes=15)).isoformat(),
            }
        )
    return rows


def test_headline_skill_suppressed_below_min_event_clusters() -> None:
    thin = MIN_DISPLAY_EVENT_CLUSTERS - 1
    metrics = evidence_metrics(_skill_rows(thin))
    scope = next(iter(metrics["scopes"].values()))

    # The headline number a dashboard would render is GONE.
    assert scope["brier_skill_vs_market"] is None
    display = scope["headline_skill"]
    assert display["status"] == "INSUFFICIENT_CLUSTERS"
    assert display["suppressed"] is True
    assert display["event_clusters"] == thin
    assert display["min_clusters"] == MIN_DISPLAY_EVENT_CLUSTERS
    assert display["brier_skill_vs_market"] is None
    # ... but the underlying computed value is preserved, not deleted.
    assert display["computed_brier_skill_vs_market"] > 0.9

    rollup = metrics["headline_skill_display"]
    assert rollup["scopes_suppressed"] == 1
    assert rollup["scopes_displayed"] == 0
    assert rollup["min_clusters"] == MIN_DISPLAY_EVENT_CLUSTERS
    assert rollup["suppressed_scopes"] == list(metrics["scopes"])


def test_headline_skill_shown_at_and_above_min_event_clusters() -> None:
    for clusters in (MIN_DISPLAY_EVENT_CLUSTERS, MIN_DISPLAY_EVENT_CLUSTERS + 5):
        metrics = evidence_metrics(_skill_rows(clusters))
        scope = next(iter(metrics["scopes"].values()))
        display = scope["headline_skill"]
        assert display["status"] == "DISPLAYED", clusters
        assert display["suppressed"] is False
        assert display["event_clusters"] == clusters
        assert scope["brier_skill_vs_market"] == pytest.approx(0.99972, abs=1e-4)
        assert display["brier_skill_vs_market"] == scope["brier_skill_vs_market"]
        assert metrics["headline_skill_display"]["scopes_suppressed"] == 0


def test_scope_without_market_benchmark_is_not_called_suppressed() -> None:
    rows = [
        {**row, "market_brier": None, "market_probability": None}
        for row in _skill_rows(MIN_DISPLAY_EVENT_CLUSTERS + 2)
    ]
    scope = next(iter(evidence_metrics(rows)["scopes"].values()))
    assert scope["brier_skill_vs_market"] is None
    assert scope["headline_skill"]["status"] == "NO_MARKET_BENCHMARK"
    assert scope["headline_skill"]["suppressed"] is False


def test_live_report_carries_the_display_gate(tmp_path) -> None:
    """The gate reaches the artifact the dashboard reads, not just the helper."""
    store, matrix = _matrix(tmp_path)
    market = _market(
        "KXBTC15M-21JUL261215-15", AS_OF + timedelta(minutes=15), AS_OF
    )
    try:
        report = matrix.run_cycle([market], states={"BTC": _state()}, as_of=AS_OF)
        store.settle_ticker(market.ticker, True, AS_OF + timedelta(minutes=16))
        rebuilt = matrix.build_report(report["cycle_id"])
        evidence = rebuilt["settled_evidence"]
        assert evidence["headline_skill_display"]["min_clusters"] == (
            MIN_DISPLAY_EVENT_CLUSTERS
        )
        # One settled forecast == one cluster: far below the minimum.
        for scope in evidence["scopes"].values():
            assert scope["headline_skill"]["status"] == "INSUFFICIENT_CLUSTERS"
            assert scope["brier_skill_vs_market"] is None
    finally:
        matrix.close()
