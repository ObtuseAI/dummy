"""Tests: phantom settlement grading, retro evidence engine, debias curve,
stage close-horizon. All hermetic — every fetcher is injected."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Forecast, MarketView, Signal, Stage, Vertical
from autonomy.reconciler import Reconciler
from autonomy.retro import (
    HourlyPriceSeries,
    RetroEvidenceEngine,
    build_weather_history_fetcher,
    candle_quote_at,
)
from autonomy.signals.market_debias import (
    MIN_BUCKET_N,
    MarketDebiasSignal,
    fit_curve,
    write_curve,
)

NOW = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)


def _ledger(tmp_path: Path) -> AutonomyLedger:
    return AutonomyLedger(tmp_path / "ledger.db")


def _signal(ticker: str, source: str = "crypto_spot_vol", p: float = 0.4) -> Signal:
    return Signal(source=source, market_ticker=ticker, probability_yes=p,
                  uncertainty=0.1, rationale="t")


# ---------------------------------------------------------------- ledger


def test_ledger_mode_column_and_forecast_queries(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record_signal(_signal("MKT-A"))                     # default live
    ledger.record_signal(_signal("MKT-B"), mode="retro")
    ledger.record_settlement("MKT-B", True)
    unsettled = ledger.unsettled_forecast_markets()
    assert unsettled == ["MKT-A"]
    split = ledger.evidence_split()
    assert split == {"live_settled": 0, "retro_settled": 1}
    ledger.record_settlement("MKT-A", False)
    split = ledger.evidence_split()
    assert split == {"live_settled": 1, "retro_settled": 1}
    ledger.close()


def test_ledger_migrates_existing_db_without_mode(tmp_path):
    import sqlite3

    db = tmp_path / "old.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE signals (id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,"
        " market_ticker TEXT NOT NULL, probability_yes REAL NOT NULL, uncertainty REAL NOT NULL,"
        " rationale TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO signals(source, market_ticker, probability_yes, uncertainty,"
                 " rationale, created_at) VALUES ('s','M',0.5,0.1,'r','2026-07-01T00:00:00+00:00')")
    conn.commit()
    conn.close()
    ledger = AutonomyLedger(db)  # must not raise; adds the mode column
    rows = ledger._conn.execute("SELECT mode FROM signals").fetchall()
    assert rows == [("live",)]
    ledger.close()


def test_unsettled_forecast_markets_age_bound(tmp_path):
    ledger = _ledger(tmp_path)
    old = Signal(source="s", market_ticker="OLD", probability_yes=0.5, uncertainty=0.1,
                 rationale="r", created_at=(NOW - timedelta(days=30)).isoformat())
    ledger.record_signal(old)
    ledger.record_signal(_signal("FRESH"))
    assert ledger.unsettled_forecast_markets(max_age_days=7) == ["FRESH"]
    ledger.close()


# ---------------------------------------------------------------- phantom sweep


def test_reconcile_forecast_settlements_batch(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record_signal(_signal("KXBTCD-26JUL0901-T70000"))
    ledger.record_signal(_signal("KXBTCD-26JUL0902-T71000"))

    pages = {
        None: {"markets": [
            {"ticker": "KXBTCD-26JUL0901-T70000", "result": "no"},
            {"ticker": "KXBTCD-26JUL0999-T9", "result": "yes"},  # never forecasted
        ], "cursor": "c2"},
        "c2": {"markets": [
            {"ticker": "KXBTCD-26JUL0902-T71000", "result": "yes"},
        ], "cursor": None},
    }
    calls: list[tuple] = []

    def fake_page(series, min_close_ts, cursor=None):
        calls.append((series, cursor))
        return pages[cursor]

    reconciler = Reconciler(ledger, fetch_market_result=lambda t: {},
                            fetch_settled_page=fake_page)
    settled = reconciler.reconcile_forecast_settlements(["KXBTCD"])
    assert sorted(settled) == [("KXBTCD-26JUL0901-T70000", False),
                               ("KXBTCD-26JUL0902-T71000", True)]
    assert ledger.unsettled_forecast_markets() == []
    # Cursor was followed.
    assert calls == [("KXBTCD", None), ("KXBTCD", "c2")]
    ledger.close()


def test_phantom_sweep_disabled_without_fetcher(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record_signal(_signal("MKT-X"))
    reconciler = Reconciler(ledger, fetch_market_result=lambda t: {})
    assert reconciler.reconcile_forecast_settlements(["KXBTCD"]) == []
    ledger.close()


def test_phantom_settlement_updates_trust_weights(tmp_path):
    from autonomy.learner import Learner

    ledger = _ledger(tmp_path)
    ticker = "KXBTCD-26JUL0901-T70000"
    ledger.record_signal(_signal(ticker, source="market_prior", p=0.5))
    ledger.record_signal(_signal(ticker, source="crypto_spot_vol", p=0.05))

    def fake_page(series, min_close_ts, cursor=None):
        return {"markets": [{"ticker": ticker, "result": "no"}], "cursor": None}

    reconciler = Reconciler(ledger, fetch_market_result=lambda t: {},
                            fetch_settled_page=fake_page)
    learner = Learner(ledger)
    for t, result_yes in reconciler.reconcile_forecast_settlements(["KXBTCD"]):
        learner.apply_settlement(t, result_yes)
    # crypto beat the market prior on a NO result -> weight above default.
    assert ledger.get_weight("crypto_spot_vol") > 1.0
    ledger.close()


# ---------------------------------------------------------------- candles


def _candle(end_ts: int, bid: float, ask: float) -> dict:
    return {"end_period_ts": end_ts,
            "yes_bid": {"close_dollars": f"{bid:.4f}"},
            "yes_ask": {"close_dollars": f"{ask:.4f}"},
            "volume_fp": "12.00"}


def test_candle_quote_at_never_looks_ahead():
    decision = 1_000_000
    candles = [_candle(decision - 3600, 0.30, 0.34),
               _candle(decision + 60, 0.90, 0.95)]  # after decision: forbidden
    quote = candle_quote_at(candles, decision)
    assert quote["yes_bid"] == 30 and quote["yes_ask"] == 34
    assert candle_quote_at([_candle(decision + 60, 0.9, 0.95)], decision) is None


def test_hourly_price_series_excludes_unclosed_candles():
    base = 1_000_000_000
    rows = [[base + i * 3600, 0, 0, 0, 60000 + (i % 2) * 120, 1.0] for i in range(60)]

    def fake_fetch(product, start_iso, end_iso, granularity):
        return rows

    series = HourlyPriceSeries("BTC-USD", base, base + 60 * 3600, fetch=fake_fetch)
    ts_mid = base + 40 * 3600 + 1800  # candle 40 not yet closed
    spot_vol = series.spot_and_vol_at(ts_mid)
    assert spot_vol is not None
    spot, vol = spot_vol
    # Last fully-closed candle is index 39 (closes at base+40h).
    assert spot == 60000 + (39 % 2) * 120
    assert vol > 0
    assert series.spot_and_vol_at(base + 3 * 3600) is None  # <24 closed candles


# ---------------------------------------------------------------- retro engine


def _crypto_settled_raw(ticker: str, close_iso: str, floor: float, result: str) -> dict:
    return {"ticker": ticker, "status": "finalized", "result": result,
            "close_time": close_iso, "strike_type": "greater", "floor_strike": floor,
            "title": "t"}


def test_retro_crypto_replay_writes_signals_and_settlement(tmp_path):
    ledger = _ledger(tmp_path)
    close_dt = NOW - timedelta(hours=5)
    ticker = "KXBTCD-26JUL0907-T62000"
    raw = _crypto_settled_raw(ticker, close_dt.isoformat(), 62000.0, "yes")
    decision_ts = int(close_dt.timestamp()) - 45 * 60

    def fake_settled(series, min_close_ts, cursor=None):
        return {"markets": [raw] if series == "KXBTCD" else [], "cursor": None}

    def fake_candles(series, tkr, start_ts, end_ts, period=60):
        return [_candle(decision_ts - 600, 0.55, 0.60)]

    base = int((NOW - timedelta(days=19)).timestamp())
    rows = [[base + i * 3600, 0, 0, 0, 63000 + (i % 3) * 40, 1.0]
            for i in range(19 * 24)]

    def fake_coinbase(product, start_iso, end_iso, granularity):
        return rows

    engine = RetroEvidenceEngine(ledger, fetch_settled_page=fake_settled,
                                 fetch_candles=fake_candles, fetch_coinbase=fake_coinbase,
                                 sleep_s=0.0, now=NOW)
    stats = engine.replay_crypto(lookback_days=2.0, max_per_series=10,
                                 series_list=["KXBTCD"])
    assert stats["written"] == 1

    rows_db = ledger._conn.execute(
        "SELECT source, mode, created_at FROM signals WHERE market_ticker=?", (ticker,)
    ).fetchall()
    sources = {r[0] for r in rows_db}
    assert sources == {"market_prior", "crypto_spot_vol"}
    assert all(r[1] == "retro" for r in rows_db)
    # Signals are timestamped at the historical decision moment.
    assert all(r[2].startswith(datetime.fromtimestamp(decision_ts, tz=timezone.utc)
                               .isoformat()[:16]) for r in rows_db)
    settlement = ledger._conn.execute(
        "SELECT result_yes FROM settlements WHERE market_ticker=?", (ticker,)).fetchone()
    assert settlement == (1,)
    assert len(engine.debias_samples) == 1
    ledger.close()


def test_retro_skips_markets_without_contemporaneous_quote(tmp_path):
    ledger = _ledger(tmp_path)
    close_dt = NOW - timedelta(hours=5)
    raw = _crypto_settled_raw("KXBTCD-26JUL0907-T62000", close_dt.isoformat(), 62000.0, "yes")
    decision_ts = int(close_dt.timestamp()) - 45 * 60

    def fake_settled(series, min_close_ts, cursor=None):
        return {"markets": [raw] if series == "KXBTCD" else [], "cursor": None}

    def fake_candles(series, tkr, start_ts, end_ts, period=60):
        return [_candle(decision_ts + 300, 0.55, 0.60)]  # only AFTER decision

    base = int((NOW - timedelta(days=19)).timestamp())
    rows = [[base + i * 3600, 0, 0, 0, 63000 + (i % 3) * 40, 1.0] for i in range(19 * 24)]
    engine = RetroEvidenceEngine(ledger, fetch_settled_page=fake_settled,
                                 fetch_candles=fake_candles,
                                 fetch_coinbase=lambda *a, **k: rows,
                                 sleep_s=0.0, now=NOW)
    stats = engine.replay_crypto(lookback_days=2.0, series_list=["KXBTCD"])
    assert stats["written"] == 0 and stats["skipped_no_quote"] == 1
    assert ledger._conn.execute("SELECT COUNT(*) FROM settlements").fetchone() == (0,)
    ledger.close()


def test_retro_never_rewrites_existing_settlement(tmp_path):
    ledger = _ledger(tmp_path)
    close_dt = NOW - timedelta(hours=5)
    ticker = "KXBTCD-26JUL0907-T62000"
    ledger.record_settlement(ticker, False)  # already graded live
    raw = _crypto_settled_raw(ticker, close_dt.isoformat(), 62000.0, "yes")

    engine = RetroEvidenceEngine(
        ledger,
        fetch_settled_page=lambda s, m, c=None: {"markets": [raw], "cursor": None},
        fetch_candles=lambda *a, **k: [], fetch_coinbase=lambda *a, **k: [],
        sleep_s=0.0, now=NOW)
    stats = engine.replay_crypto(lookback_days=2.0, series_list=["KXBTCD"])
    assert stats["skipped_already_settled"] == 1 and stats["written"] == 0
    row = ledger._conn.execute("SELECT result_yes FROM settlements WHERE market_ticker=?",
                               (ticker,)).fetchone()
    assert row == (0,)  # original result untouched
    ledger.close()


def test_retro_appends_empirical_challenger_to_existing_settlement(tmp_path):
    ledger = _ledger(tmp_path)
    close_dt = NOW - timedelta(hours=5)
    ticker = "KXBTCD-26JUL0907-T62000"
    ledger.record_settlement(ticker, False)
    raw = _crypto_settled_raw(ticker, close_dt.isoformat(), 62000.0, "yes")
    base = int((NOW - timedelta(days=19)).timestamp())
    rows = [[base + i * 3600, 0, 0, 0, 60_000 * (1.0002**i), 1.0]
            for i in range(19 * 24)]
    engine = RetroEvidenceEngine(
        ledger,
        fetch_settled_page=lambda s, m, c=None: {"markets": [raw], "cursor": None},
        fetch_candles=lambda *a, **k: [],
        fetch_coinbase=lambda *a, **k: rows,
        sleep_s=0.0,
        now=NOW,
    )
    first = engine.replay_crypto_challengers(
        lookback_days=2.0, series_list=["KXBTCD"],
    )
    second = engine.replay_crypto_challengers(
        lookback_days=2.0, series_list=["KXBTCD"],
    )
    assert first["written"] == 1
    assert second["written"] == 0 and second["skipped_existing_signal"] == 1
    stored = ledger._conn.execute(
        "SELECT mode,features FROM signals WHERE source='crypto_empirical_regime'"
    ).fetchone()
    assert stored is not None and stored[0] == "retro"
    assert '"retro_point_in_time":true' in stored[1]
    # Existing immutable settlement wins over the contradictory listing fixture.
    assert ledger.settlement_result(ticker) is False
    ledger.close()


def test_retro_appends_dvol_challenger_without_lookahead(tmp_path):
    ledger = _ledger(tmp_path)
    close_dt = NOW - timedelta(hours=5)
    ticker = "KXBTCD-26JUL0907-T62000"
    ledger.record_settlement(ticker, False)
    raw = _crypto_settled_raw(ticker, close_dt.isoformat(), 62000.0, "yes")
    decision_ts = int(close_dt.timestamp()) - 45 * 60
    base = int((NOW - timedelta(days=19)).timestamp())
    coinbase_rows = [
        [base + i * 3600, 0, 0, 0, 60_000 * (1.0002**i), 1.0]
        for i in range(19 * 24)
    ]
    # Row 1 is fully closed before the decision; row 2 is still in progress
    # and must not leak its much larger value into the retro signal.
    dvol_rows = [
        [(decision_ts - 7200) * 1000, 0, 0, 0, 42.0],
        [(decision_ts - 1800) * 1000, 0, 0, 0, 99.0],
    ]
    engine = RetroEvidenceEngine(
        ledger,
        fetch_settled_page=lambda s, m, c=None: {"markets": [raw], "cursor": None},
        fetch_candles=lambda *a, **k: [],
        fetch_coinbase=lambda *a, **k: coinbase_rows,
        fetch_deribit=lambda *a, **k: {"result": {"data": dvol_rows}},
        sleep_s=0.0,
        now=NOW,
    )
    first = engine.replay_crypto_dvol_challenger(
        lookback_days=2.0, series_list=["KXBTCD"],
    )
    second = engine.replay_crypto_dvol_challenger(
        lookback_days=2.0, series_list=["KXBTCD"],
    )
    assert first["written"] == 1
    assert second["written"] == 0 and second["skipped_existing_signal"] == 1
    stored = ledger._conn.execute(
        "SELECT mode,features FROM signals WHERE source='crypto_dvol_implied'"
    ).fetchone()
    assert stored is not None and stored[0] == "retro"
    assert '"retro_point_in_time":true' in stored[1]
    assert '"deribit_dvol":42.0' in stored[1]
    assert '"deribit_dvol":99.0' not in stored[1]
    assert ledger.settlement_result(ticker) is False
    ledger.close()


def test_retro_appends_hourly_technical_challenger(tmp_path):
    ledger = _ledger(tmp_path)
    close_dt = NOW - timedelta(hours=5)
    ticker = "KXBTCD-26JUL0907-T62000"
    ledger.record_settlement(ticker, False)
    raw = _crypto_settled_raw(ticker, close_dt.isoformat(), 62000.0, "yes")
    base = int((NOW - timedelta(days=19)).timestamp())
    rows = [
        [base + i * 3600, 0, 0, 0, 60_000 * (1.0002**i), 1.0]
        for i in range(19 * 24)
    ]
    engine = RetroEvidenceEngine(
        ledger,
        fetch_settled_page=lambda s, m, c=None: {"markets": [raw], "cursor": None},
        fetch_candles=lambda *a, **k: [],
        fetch_coinbase=lambda *a, **k: rows,
        sleep_s=0.0,
        now=NOW,
    )
    first = engine.replay_crypto_technical_challenger(
        lookback_days=2.0, series_list=["KXBTCD"],
    )
    second = engine.replay_crypto_technical_challenger(
        lookback_days=2.0, series_list=["KXBTCD"],
    )
    assert first["written"] == 1
    assert second["written"] == 0 and second["skipped_existing_signal"] == 1
    stored = ledger._conn.execute(
        "SELECT mode,features FROM signals WHERE source='crypto_technical_composite'"
    ).fetchone()
    assert stored is not None and stored[0] == "retro"
    assert '"retro_point_in_time":true' in stored[1]
    assert '"minute_resolution":0.0' in stored[1]
    assert ledger.settlement_result(ticker) is False
    ledger.close()


def test_retro_weather_replay_uses_historical_forecast(tmp_path):
    ledger = _ledger(tmp_path)
    event_date = (NOW - timedelta(days=3)).strftime("%Y-%m-%d")
    date_token = (NOW - timedelta(days=3)).strftime("%d").rjust(2, "0")
    mon = (NOW - timedelta(days=3)).strftime("%b").upper()
    yy = (NOW - timedelta(days=3)).strftime("%y")
    ticker = f"KXHIGHNY-{yy}{mon}{date_token}-B83.5"
    close_iso = (NOW - timedelta(days=2, hours=7)).isoformat()
    raw = {"ticker": ticker, "status": "finalized", "result": "yes", "close_time": close_iso,
           "strike_type": "between", "floor_strike": 83, "cap_strike": 84, "title": "t"}

    def fake_settled(series, min_close_ts, cursor=None):
        return {"markets": [raw] if series == "KXHIGHNY" else [], "cursor": None}

    def fake_candles(series, tkr, start_ts, end_ts, period=60):
        return [_candle(start_ts + 3600, 0.20, 0.26)]

    def fake_history(lat, lon, start, end, kind):
        # Three models all forecasting ~83.6F for the event day.
        return {"time": [event_date],
                "temperature_2m_max_gfs_seamless": [83.4],
                "temperature_2m_max_ecmwf_ifs025": [83.7],
                "temperature_2m_max_icon_seamless": [83.8]}

    engine = RetroEvidenceEngine(ledger, fetch_settled_page=fake_settled,
                                 fetch_candles=fake_candles,
                                 fetch_weather_history=fake_history,
                                 sleep_s=0.0, now=NOW)
    stats = engine.replay_weather(lookback_days=7.0, series_list=["KXHIGHNY"])
    assert stats["written"] == 1
    sources = {r[0] for r in ledger._conn.execute(
        "SELECT source FROM signals WHERE market_ticker=?", (ticker,)).fetchall()}
    assert sources == {"market_prior", "weather_openmeteo"}
    ledger.close()


def test_weather_history_fetcher_routes_by_city():
    def fake_history(lat, lon, start, end, kind):
        # Only NY gets data.
        if abs(lat - 40.7794) < 1e-6:
            return {"time": ["2026-07-05"], "temperature_2m_max_gfs_seamless": [88.0]}
        return {"time": [], }

    fetcher = build_weather_history_fetcher(7, today=NOW, fetch_history=fake_history)
    assert fetcher(40.7794, -73.9692, "2026-07-05", "HIGH") == [88.0]
    assert fetcher(40.7794, -73.9692, "2026-07-04", "HIGH") == []
    assert fetcher(25.7906, -80.3164, "2026-07-05", "HIGH") == []


# ---------------------------------------------------------------- debias


def test_fit_curve_and_debias_signal(tmp_path):
    # 150 samples with mid ~0.32 of which 40 resolved YES -> yes_rate ~0.267.
    samples = [(0.32, 1 if i < 40 else 0) for i in range(150)]
    curve = fit_curve(samples)
    path = write_curve(curve, tmp_path / "curve.json")
    signal_source = MarketDebiasSignal(curve_path=path)

    market = MarketView(ticker="X", title="", vertical=Vertical.CRYPTO, status="active",
                        close_time=NOW.isoformat(), yes_bid=30, yes_ask=34,
                        no_bid=66, no_ask=70, volume=100, liquidity=100)
    assert signal_source.applicable(market)
    signal = signal_source.generate(market)
    assert signal is not None
    assert abs(signal.probability_yes - 40 / 150) < 0.01
    assert signal.features["bucket_n"] == 150


def test_debias_signal_fail_closed(tmp_path):
    # Thin bucket -> no opinion.
    curve = fit_curve([(0.32, 1)] * (MIN_BUCKET_N - 1))
    path = write_curve(curve, tmp_path / "thin.json")
    source = MarketDebiasSignal(curve_path=path)
    market = MarketView(ticker="X", title="", vertical=Vertical.CRYPTO, status="active",
                        close_time=NOW.isoformat(), yes_bid=30, yes_ask=34,
                        no_bid=66, no_ask=70, volume=100, liquidity=100)
    assert source.generate(market) is None
    # Missing artifact -> inapplicable.
    missing = MarketDebiasSignal(curve_path=tmp_path / "nope.json")
    assert not missing.applicable(market)


# ---------------------------------------------------------------- contested


def test_tracker_contested_record_and_weight_cap():
    from autonomy.backtest import MIN_CONTESTED_N, SourceScoreTracker

    tracker = SourceScoreTracker("pretender")
    # Overall record looks great: agrees with a well-priced market 100 times.
    for _ in range(100):
        tracker.observe(0.05, 0, market_brier=(0.05 - 0) ** 2, market_p=0.05)
    # But when it disagrees, it loses: market at 0.30, source at 0.60, result NO.
    for _ in range(MIN_CONTESTED_N):
        tracker.observe(0.60, 0, market_brier=(0.30 - 0) ** 2, market_p=0.30)
    summary = tracker.summary()
    assert summary["contested_n"] == MIN_CONTESTED_N
    assert summary["contested_beat_rate"] == 0.0
    # The contested cap must drag the weight below neutral despite the shiny
    # overall Brier.
    assert tracker.derived_weight() < 0.5

    winner = SourceScoreTracker("real_edge")
    for _ in range(MIN_CONTESTED_N):
        winner.observe(0.80, 1, market_brier=(0.55 - 1) ** 2, market_p=0.55)
    assert winner.summary()["contested_beat_rate"] == 1.0
    assert winner.derived_weight() > 1.0


def test_canary_gate_requires_contested_beater(tmp_path):
    from autonomy.backtest import run_backtest
    from autonomy.canary import evaluate_canary_readiness

    ledger = _ledger(tmp_path)
    # 30 settled markets where the source AGREES with the market (no contested
    # record at all) — must NOT qualify as a beater even though it's "right".
    for i in range(30):
        t = f"AGREE{i}"
        ledger.record_signal(_signal(t, source="market_prior", p=0.05))
        ledger.record_signal(_signal(t, source="conformist", p=0.06))
        ledger.record_settlement(t, False)
    run_backtest(ledger, bootstrap_weights=True)
    readiness = evaluate_canary_readiness(ledger, balance_cents=5000)
    assert readiness.ready is False
    assert any("disagrees" in b for b in readiness.blockers)
    ledger.close()


# ---------------------------------------------------------------- stage horizon


def _forecast(ticker: str, p: float = 0.70) -> Forecast:
    return Forecast(market_ticker=ticker, probability_yes=p, uncertainty=0.10,
                    sources_used={"crypto_spot_vol": 1.0}, market_implied_yes=0.52,
                    edge_yes=p - 0.52, rationale="t")


def _risk_state(stage: Stage):
    from autonomy.risk_brain import RiskState

    return RiskState(bankroll_cents=100_000, equity_peak_cents=100_000, stage=stage,
                     open_exposure_cents=0, open_markets=0, daily_pnl_cents=0,
                     settled_count_at_stage=0, realized_pnl_per_contract_cents=0.0)


def _far_market(days_out: float) -> MarketView:
    return MarketView(ticker="KXNFLGAME-26AUG13DENSF-DEN", title="", vertical=Vertical.SPORTS,
                      status="active",
                      close_time=(datetime.now(timezone.utc) + timedelta(days=days_out)).isoformat(),
                      yes_bid=50, yes_ask=55, no_bid=45, no_ask=50, volume=500, liquidity=500)


def test_allocator_stage_horizon_blocks_far_dated_markets():
    from autonomy.allocator import Allocator
    from autonomy.risk_brain import RiskBrain

    allocator = Allocator(RiskBrain())
    market = _far_market(35.0)
    decision = allocator.decide(market, _forecast(market.ticker), _risk_state(Stage.CANARY))
    assert decision.action.value == "ABSTAIN"
    assert "stage horizon" in decision.abstain_reason

    near = _far_market(2.0)
    decision_near = allocator.decide(near, _forecast(near.ticker), _risk_state(Stage.CANARY))
    assert "stage horizon" not in decision_near.abstain_reason

    cruise = allocator.decide(market, _forecast(market.ticker), _risk_state(Stage.CRUISE))
    assert "stage horizon" not in cruise.abstain_reason
