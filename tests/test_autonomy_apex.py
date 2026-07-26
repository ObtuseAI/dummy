"""Tests: sportsbook consensus + steam, crypto challenger, per-vertical trust,
tape reader, capital-velocity ranking, circuit breakers, self-recalibration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Forecast, MarketView, Signal, Vertical
from autonomy.signals.sportsbook import SportsbookConsensusSignal, american_to_prob, devig_two_way
from autonomy.sports.espn import EspnClient, _american, parse_scoreboard

NOW = datetime.now(timezone.utc)


def _market(ticker: str, vertical=Vertical.SPORTS, hours_out: float = 6.0) -> MarketView:
    return MarketView(ticker=ticker, title="", vertical=vertical, status="active",
                      close_time=(NOW + timedelta(hours=hours_out)).isoformat(),
                      yes_bid=45, yes_ask=55, no_bid=45, no_ask=55, volume=500, liquidity=500)


# ---------------------------------------------------------------- espn odds


def _event_with_ml(home, away, home_close, away_close, home_open=None, away_open=None, state="pre"):
    def comp_side(abbr, ha):
        return {"homeAway": ha, "team": {"abbreviation": abbr}, "winner": None}

    ml = {"home": {"close": {"odds": home_close}}, "away": {"close": {"odds": away_close}}}
    if home_open is not None:
        ml["home"]["open"] = {"odds": home_open}
    if away_open is not None:
        ml["away"]["open"] = {"odds": away_open}
    return {
        "id": "77", "date": "2026-07-09T22:10Z",
        "competitions": [{
            "status": {"type": {"state": state}},
            "competitors": [comp_side(home, "home"), comp_side(away, "away")],
            "odds": [{"provider": {"name": "DraftKings"}, "moneyline": ml}],
        }],
    }


def test_american_odds_parser():
    assert _american("+101") == 101
    assert _american("-149") == -149
    assert _american(-103.0) == -103
    assert _american("+120.0") == 120
    assert _american("EVEN") == 100
    assert _american(-103.5) is None
    assert _american(None) is None
    assert _american("n/a") is None


def test_parse_scoreboard_extracts_moneylines():
    games = parse_scoreboard("mlb", {"events": [
        _event_with_ml("NYM", "KC", "-149", "+124", home_open="-140", away_open="+118")]})
    g = games[0]
    assert g.home_ml == -149 and g.away_ml == 124
    assert g.home_ml_open == -140 and g.away_ml_open == 118
    assert g.odds_provider == "DraftKings"


def test_devig_two_way_removes_margin():
    # -149 / +124: raw implied sums > 1; de-vigged must sum to exactly 1.
    p_home = devig_two_way(-149, 124)
    p_away = devig_two_way(124, -149)
    assert abs(p_home + p_away - 1.0) < 1e-9
    assert p_home > 0.5 > p_away
    assert american_to_prob(100) == 0.5
    assert devig_two_way(None, 124) is None


# ---------------------------------------------------------------- sportsbook signal


def test_sportsbook_signal_devig_and_steam():
    scoreboard = {"events": [
        _event_with_ml("NYM", "KC", "-149", "+124", home_open="-120", away_open="+100")]}
    client = EspnClient(fetch_scoreboard=lambda _league, _date: scoreboard)
    source = SportsbookConsensusSignal(espn=client)
    market = _market("KXMLBGAME-26JUL091910KCNYM-NYM")
    assert source.applicable(market)
    signal = source.generate(market)
    assert signal is not None
    devig = devig_two_way(-149, 124)
    assert abs(signal.probability_yes - devig) < 1e-9
    # Line moved from -120 to -149 on NYM: steam toward the subject.
    assert signal.features["steam_since_open"] > 0
    assert "DraftKings" in signal.rationale


def test_sportsbook_signal_fail_closed():
    # No odds block at all.
    def comp_side(abbr, ha):
        return {"homeAway": ha, "team": {"abbreviation": abbr}, "winner": None}

    bare = {"events": [{"id": "1", "date": "2026-07-09T22:10Z", "competitions": [{
        "status": {"type": {"state": "pre"}},
        "competitors": [comp_side("NYM", "home"), comp_side("KC", "away")]}]}]}
    source = SportsbookConsensusSignal(espn=EspnClient(fetch_scoreboard=lambda _league, _date: bare))
    assert source.generate(_market("KXMLBGAME-26JUL091910KCNYM-NYM")) is None
    # Started game -> stale line -> no opinion.
    started = {"events": [_event_with_ml("NYM", "KC", "-149", "+124", state="in")]}
    source2 = SportsbookConsensusSignal(espn=EspnClient(fetch_scoreboard=lambda _league, _date: started))
    assert source2.generate(_market("KXMLBGAME-26JUL091910KCNYM-NYM")) is None


# ---------------------------------------------------------------- crypto challenger


def test_crypto_challenger_fat_tails_and_ewma():
    from autonomy.signals.crypto_spot import (
        CryptoEwmaTailSignal,
        CryptoSpotVolSignal,
        ewma_spot_and_vol,
    )

    # EWMA reacts to a recent vol burst more than the flat window does.
    calm = [60000.0 * (1.0 + (0.0001 if i % 2 else -0.0001)) for i in range(150)]
    burst = [60000.0 * (1.0 + (0.01 if i % 2 else -0.01)) for i in range(18)]
    closes = burst + calm  # most-recent-first: burst is the newest 18 hours
    _spot, vol_ewma = ewma_spot_and_vol("BTC", closes=closes)
    assert vol_ewma > 0

    # Far-OTM strike: the fat-tail mixture must assign MORE probability than
    # the single normal (that's the point of the tails).
    def fixed(asset):
        return 60000.0, 0.50  # 50% annualized

    # ~2.5 sigma OTM at this vol/horizon: the regime where tail shape matters
    # and neither model is pinned to the probability clamp.
    raw = {"strike_type": "greater", "floor_strike": 62000}
    market = MarketView(ticker="KXBTCD-26JUL0917-T62000", title="", vertical=Vertical.CRYPTO,
                        status="active", close_time=(NOW + timedelta(hours=6)).isoformat(),
                        yes_bid=1, yes_ask=3, no_bid=97, no_ask=99, volume=100, liquidity=100,
                        raw=raw)
    champion = CryptoSpotVolSignal(fetch_spot_and_vol=fixed).generate(market)
    challenger = CryptoEwmaTailSignal(fetch_spot_and_vol=fixed).generate(market)
    assert champion is not None and challenger is not None
    assert challenger.source == "crypto_ewma_t" != champion.source
    assert challenger.probability_yes > champion.probability_yes  # fatter tail


# ---------------------------------------------------------------- per-vertical trust


def test_scoped_trust_lookup_and_learner(tmp_path):
    from autonomy.learner import Learner

    ledger = AutonomyLedger(tmp_path / "l.db")
    # Global weight exists; no scoped row yet -> fallback.
    ledger.update_weight("src", 2.0)
    assert ledger.get_weight_scoped("src", "CRYPTO") == 2.0
    ledger.update_weight("src@CRYPTO", 0.5)
    assert ledger.get_weight_scoped("src", "CRYPTO") == 0.5
    assert ledger.get_weight_scoped("src", "WEATHER") == 2.0

    # Learner writes both global and scoped rows on settlement.
    ticker = "KXBTCD-26JUL0901-T70000"
    ledger.record_signal(Signal(source="market_prior", market_ticker=ticker,
                                probability_yes=0.5, uncertainty=0.1, rationale=""))
    ledger.record_signal(Signal(source="alpha", market_ticker=ticker,
                                probability_yes=0.05, uncertainty=0.1, rationale=""))
    Learner(ledger).apply_settlement(ticker, False)
    assert ledger.get_weight("alpha") > 1.0
    assert ledger.get_weight("alpha@CRYPTO", default=0.0) > 1.0
    from autonomy.taxonomy import scope_weight_key

    exact_key = scope_weight_key("alpha", ticker, {})
    assert ledger.get_weight(exact_key, default=0.0) > 1.0
    assert ledger.get_weight_for_signal("alpha", "CRYPTO", ticker, {}) == ledger.get_weight(exact_key)
    ledger.close()


def test_forecaster_uses_scoped_weight(tmp_path):
    from autonomy.forecaster import EnsembleForecaster

    ledger = AutonomyLedger(tmp_path / "l.db")
    ledger.update_weight("a", 1.0)
    ledger.update_weight("a@CRYPTO", 8.0)  # crypto authority
    market = _market("KXBTCD-26JUL0917-T60000", vertical=Vertical.CRYPTO)
    signals = [
        Signal(source="a", market_ticker=market.ticker, probability_yes=0.9,
               uncertainty=0.1, rationale=""),
        Signal(source="b", market_ticker=market.ticker, probability_yes=0.1,
               uncertainty=0.1, rationale=""),
    ]
    fused = EnsembleForecaster(ledger).fuse(market, signals)
    # Scoped 8x trust must drag the fusion decisively toward source a.
    assert fused.probability_yes > 0.7

    # Exact scope overrides broader vertical authority once that scope has
    # earned its own settled record.
    from autonomy.taxonomy import scope_weight_key

    ledger.update_weight(scope_weight_key("a", market.ticker, {}), 0.05)
    fused = EnsembleForecaster(ledger).fuse(market, signals)
    assert fused.probability_yes < 0.3
    ledger.close()


def test_forecaster_prefetched_weights_avoid_per_signal_ledger_reads(tmp_path):
    from autonomy.forecaster import EnsembleForecaster
    from autonomy.taxonomy import scope_weight_key

    ledger = AutonomyLedger(tmp_path / "l.db")
    market = _market("KXBTCD-26JUL0917-T60000", vertical=Vertical.CRYPTO)
    signals = [
        Signal(
            source="a",
            market_ticker=market.ticker,
            probability_yes=0.9,
            uncertainty=0.1,
            rationale="",
        ),
        Signal(
            source="b",
            market_ticker=market.ticker,
            probability_yes=0.1,
            uncertainty=0.1,
            rationale="",
        ),
    ]
    weights = {
        "a": 1.0,
        "a@CRYPTO": 2.0,
        scope_weight_key("a", market.ticker, {}): 8.0,
        "b": 1.0,
    }

    def unexpected_read(*_args, **_kwargs):
        raise AssertionError("prefetched fusion must not query trust rows")

    ledger.get_weight_for_signal = unexpected_read
    ledger.get_weight_scoped = unexpected_read
    ledger.get_weight = unexpected_read
    fused = EnsembleForecaster(ledger, weights=weights).fuse(market, signals)

    assert fused is not None and fused.probability_yes > 0.7
    ledger.close()


def test_backtest_bootstraps_scoped_weights(tmp_path, monkeypatch):
    import autonomy.backtest as backtest
    from autonomy.backtest import run_backtest

    real_gate = backtest._recal_oos_gate
    monkeypatch.setattr(
        backtest,
        "_recal_oos_gate",
        lambda conn, signals, settlements, incumbent: real_gate(
            conn,
            signals,
            settlements,
            incumbent,
            holdout_fraction=0.25,
            min_holdout=1,
            min_holdout_clusters=1,
        ),
    )
    ledger = AutonomyLedger(tmp_path / "l.db")
    observed_base = datetime.now(timezone.utc) - timedelta(days=1)
    settled_base = datetime.now(timezone.utc) + timedelta(hours=1)
    # KXMLBGAME (SPORTS) as the second vertical: WEATHER is retired (Wave-82),
    # so a weather-scoped row would now be purged rather than bootstrapped.
    for i, (ticker, result) in enumerate([("KXBTCD-A", True), ("KXBTCD-B", False),
                                          ("KXMLBGAME-C", True),
                                          ("KXHIGHNY-D", True)]):
        observed_at = (observed_base + timedelta(minutes=i)).isoformat()
        ledger.record_signal(Signal(source="market_prior", market_ticker=ticker,
                                    probability_yes=0.5, uncertainty=0.1, rationale="",
                                    created_at=observed_at))
        ledger.record_signal(Signal(source="alpha", market_ticker=ticker,
                                    probability_yes=0.9 if result else 0.1,
                                    uncertainty=0.1, rationale="",
                                    created_at=observed_at))
        ledger.record_settlement(
            ticker,
            result,
            settled_at=(settled_base + timedelta(hours=i)).isoformat(),
        )
    report = run_backtest(ledger, bootstrap_weights=True)
    assert report["recal_oos_gate"]["held_out_improvement_verified"] is True
    assert "alpha@CRYPTO" in report["derived_weights_by_vertical"]
    assert "alpha@SPORTS" in report["derived_weights_by_vertical"]
    # Retired-vertical evidence earns no live scoped weight (Wave-82 extension).
    assert "alpha@WEATHER" not in report["derived_weights_by_vertical"]
    assert ledger.get_weight("alpha@WEATHER", default=0.0) == 0.0
    assert ledger.get_weight("alpha@CRYPTO", default=0.0) > 1.0
    assert any(key.startswith("scope:alpha|") for key in ledger.all_weights())
    ledger.close()


# ---------------------------------------------------------------- tape


def _tape_candle(end_ts: int, bid_c: float, ask_c: float, vol: float) -> dict:
    return {"end_period_ts": end_ts,
            "yes_bid": {"close_dollars": f"{bid_c / 100:.4f}"},
            "yes_ask": {"close_dollars": f"{ask_c / 100:.4f}"},
            "volume_fp": f"{vol:.2f}"}


def test_tape_features_and_describe():
    from autonomy.tape import describe_tape, tape_features

    now_ts = 1_800_000_000
    candles = []
    # Two hours of 1-min candles drifting from ~30c up to ~42c, volume mostly
    # in the last 15 minutes.
    for i in range(120):
        ts = now_ts - (120 - i) * 60
        mid = 30 + i * 0.1
        vol = 5.0 if i >= 105 else 0.5
        candles.append(_tape_candle(ts, mid - 1, mid + 1, vol))

    def fake_fetch(series, ticker, start_ts, end_ts, period=1):
        return candles

    features = tape_features("KXBTCD", "KXBTCD-X", fetch_candles=fake_fetch, now_ts=now_ts)
    assert features is not None
    assert features["momentum_15m_cents"] > 0
    assert features["momentum_60m_cents"] > features["momentum_15m_cents"]
    assert features["range_position"] == 1.0  # at the top of its 2h range
    assert features["volume_surge_15m"] > 3.0
    line = describe_tape(features)
    assert "15m move" in line and "range" in line

    # Fail-closed on thin tape.
    assert tape_features("KXBTCD", "X", fetch_candles=lambda *a, **k: [], now_ts=now_ts) is None
    assert describe_tape(None) == ""


# ---------------------------------------------------------------- velocity


def test_edge_velocity_prefers_near_dated():
    from autonomy.brain import edge_velocity

    near = _market("A", hours_out=1.0)
    far = _market("B", hours_out=100.0)

    def forecast(edge):
        return Forecast(market_ticker="X", probability_yes=0.5 + edge, uncertainty=0.1,
                        sources_used={}, market_implied_yes=0.5, edge_yes=edge, rationale="")

    # 3c edge in 1h must outrank 5c edge in 100h; a huge slow edge still wins.
    assert edge_velocity(near, forecast(0.03)) > edge_velocity(far, forecast(0.05))
    assert edge_velocity(far, forecast(0.40)) > edge_velocity(near, forecast(0.03))


# ---------------------------------------------------------------- breakers


class _FlakySource:
    name = "flaky"

    def __init__(self):
        self.calls = 0
        self.fail = True

    def applicable(self, market):
        return True

    def generate(self, market):
        self.calls += 1
        if self.fail:
            raise RuntimeError("upstream dead")
        return Signal(source=self.name, market_ticker=market.ticker,
                      probability_yes=0.5, uncertainty=0.1, rationale="ok")


def test_registry_circuit_breaker_trips_and_recovers(tmp_path):
    from autonomy.signals.base import BREAKER_THRESHOLD, QUARANTINE_CYCLES, SourceRegistry

    registry = SourceRegistry(health_path=tmp_path / "health.json")
    flaky = _FlakySource()
    registry.register(flaky)
    market = _market("KXBTCD-26JUL0917-T60000", vertical=Vertical.CRYPTO)

    # Trip the breaker with consecutive failures.
    for _ in range(BREAKER_THRESHOLD):
        assert list(registry.signals_for(market)) == []
    assert registry.source_health()["flaky"]["quarantine"] == QUARANTINE_CYCLES

    # While quarantined the source is not even called.
    before = flaky.calls
    assert list(registry.signals_for(market)) == []
    assert flaky.calls == before

    # Quarantine counts down per cycle; after it expires the source retries
    # and a clean success resets its record.
    flaky.fail = False
    for _ in range(QUARANTINE_CYCLES):
        registry.on_cycle_start()
    signals = list(registry.signals_for(market))
    assert len(signals) == 1
    assert registry.source_health()["flaky"]["fails"] == 0

    # Health state persists across a fresh registry (daemon --once pattern).
    registry2 = SourceRegistry(health_path=tmp_path / "health.json")
    assert "flaky" in registry2.source_health()


# ---------------------------------------------------------------- maintenance


def _minimal_brain(tmp_path, exchange_status_fn, *, market_count=1):
    """Full brain with hermetic fakes: one juicy market, no network."""
    import asyncio  # noqa: F401

    from autonomy.brain import PredatorBrain
    from autonomy.executor import Executor
    from autonomy.learner import Learner
    from autonomy.ontology import SessionMode
    from autonomy.reconciler import Reconciler
    from autonomy.risk_brain import RiskBrain
    from autonomy.scanner import MarketScanner
    from autonomy.signals.base import SourceRegistry

    ledger = AutonomyLedger(tmp_path / "l.db")

    class _Src:
        name = "alpha"

        def applicable(self, market):
            return True

        def generate(self, market):
            return Signal(source=self.name, market_ticker=market.ticker,
                          probability_yes=0.80, uncertainty=0.05, rationale="t")

    registry = SourceRegistry()
    registry.register(_Src())
    raw_markets = [
        {
            "ticker": f"KXBTCD-26JUL0917-T{60000 + index * 1000}",
            "title": "t",
            "status": "active",
            "close_time": (NOW + timedelta(hours=2)).isoformat(),
            "yes_bid": 40,
            "yes_ask": 45,
            "no_bid": 55,
            "no_ask": 60,
            "volume": 500,
            "liquidity": 500,
        }
        for index in range(market_count)
    ]
    scanner = MarketScanner(fetch_series=lambda s: {"markets": raw_markets},
                            watchlist=["KXBTCD"])
    brain = PredatorBrain(
        mode=SessionMode.SHADOW, ledger=ledger, registry=registry, scanner=scanner,
        risk_brain=RiskBrain(state_path=tmp_path / "risk.json"),
        executor=Executor(SessionMode.SHADOW, session_path=tmp_path / "s.json",
                          kill_path=tmp_path / "KILL"),
        reconciler=Reconciler(ledger, fetch_market_result=lambda t: {}),
        learner=Learner(ledger),
        exchange_status_fn=exchange_status_fn,
    )
    return brain, ledger


def test_cycle_skips_cleanly_during_exchange_maintenance(tmp_path):
    import asyncio

    brain, ledger = _minimal_brain(
        tmp_path, lambda: {"exchange_active": False, "trading_active": False,
                           "maintenance_windows": [{"start": "x", "end": "y"}]})
    report = asyncio.run(brain.run_cycle())
    assert report.status == "CYCLE_SKIPPED_EXCHANGE_MAINTENANCE"
    assert report.markets_scanned == 0 and report.orders_placed == 0
    assert any("maintenance_windows" in n for n in report.notes)
    ledger.close()


def test_cycle_learns_but_never_orders_while_trading_halted(tmp_path):
    import asyncio

    brain, ledger = _minimal_brain(
        tmp_path, lambda: {"exchange_active": True, "trading_active": False})
    report = asyncio.run(brain.run_cycle())
    assert report.status == "CYCLE_OK"
    assert report.trading_halted is True
    assert report.markets_scanned == 1 and report.signals_generated >= 1  # kept learning
    assert report.orders_placed == 0 and report.decisions_made == 0  # placed nothing
    assert "trading_halted_orders_skipped" in report.notes
    ledger.close()


def test_cycle_batches_signal_and_pick_phase_writes(tmp_path):
    import asyncio

    brain, ledger = _minimal_brain(
        tmp_path,
        lambda: {"exchange_active": True, "trading_active": False},
        market_count=2,
    )
    original = ledger.record_signals
    batches = []

    def capture(signals, *args, **kwargs):
        batches.append([signal.source for signal in signals])
        return original(signals, *args, **kwargs)

    ledger.record_signals = capture
    report = asyncio.run(brain.run_cycle())

    assert report.status == "CYCLE_OK"
    alpha_batches = [batch for batch in batches if "alpha" in batch]
    assert alpha_batches == [["alpha", "alpha"]]
    fused_batches = [batch for batch in batches if "fused_forecast" in batch]
    assert fused_batches == [["fused_forecast", "fused_forecast"]]
    ledger.close()


def test_cycle_proceeds_when_status_probe_fails(tmp_path, monkeypatch):
    import asyncio
    from autonomy.adverse_selection import MakerAdverseSelectionEvidence

    monkeypatch.setattr(
        "autonomy.adverse_selection.load_maker_adverse_selection_evidence",
        lambda: MakerAdverseSelectionEvidence(
            haircut_cents=0.0,
            generated_at=datetime.now(timezone.utc).isoformat(),
            source_report_sha256="a" * 64,
            filled_clusters=1,
            unfilled_clusters=1,
        ),
    )

    def boom():
        raise RuntimeError("status endpoint down")

    brain, ledger = _minimal_brain(tmp_path, boom)
    report = asyncio.run(brain.run_cycle())
    # Unknown is not down: the cycle runs and trades normally.
    assert report.status == "CYCLE_OK"
    assert report.trading_halted is False
    assert report.orders_placed == 1
    ledger.close()


def test_fetch_exchange_status_shapes(monkeypatch):
    from autonomy import exchange_status

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _Httpx:
        @staticmethod
        def get(url, timeout=10):
            if url.endswith("/exchange/status"):
                return _Resp({"exchange_active": True, "trading_active": False})
            return _Resp({"schedule": {"maintenance_windows": [{"start": "s"}]}})

    monkeypatch.setattr("httpx.get", _Httpx.get)
    status = exchange_status.fetch_exchange_status()
    assert status == {"exchange_active": True, "trading_active": False,
                      "maintenance_windows": [{"start": "s"}]}


# ---------------------------------------------------------------- live-path safety


def test_run_coro_sync_inside_and_outside_event_loop():
    import asyncio

    from autonomy.session import _run_coro_sync

    async def value():
        return 42

    # Outside any loop.
    assert _run_coro_sync(value()) == 42

    # Inside a running loop (the live brain's exact call pattern).
    async def caller():
        return _run_coro_sync(value())

    assert asyncio.run(caller()) == 42


def test_open_decisions_scope_separates_books(tmp_path):
    from autonomy.ontology import OutcomeKind, TradeOutcome

    ledger = AutonomyLedger(tmp_path / "l.db")

    def _decision(decision_id, ticker):
        ledger._conn.execute(
            "INSERT INTO decisions(decision_id, market_ticker, action, side, price_cents, count,"
            " ev_cents, kelly, notional_cents, probability_yes, sources_used, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (decision_id, ticker, "BUY_YES", "yes", 40, 1, 5.0, 0.1, 40, 0.6, "{}",
             "2026-07-09T00:00:00+00:00"))
        ledger._conn.commit()

    _decision("d-shadow", "MKT-S")
    _decision("d-live", "MKT-L")
    ledger.record_outcome(TradeOutcome(
        decision_id="d-shadow", market_ticker="MKT-S", kind=OutcomeKind.SHADOW,
        order_id="shadow-d-shadow", fill_count=1, fill_price_cents=40, pnl_cents=None,
        broker_contacted=False))
    ledger.record_outcome(TradeOutcome(
        decision_id="d-live", market_ticker="MKT-L", kind=OutcomeKind.ACCEPTED,
        order_id="real-123", fill_count=0, fill_price_cents=40, pnl_cents=None,
        broker_contacted=True))

    assert {p["market_ticker"] for p in ledger.open_decisions()} == {"MKT-S", "MKT-L"}
    assert {p["market_ticker"] for p in ledger.open_decisions("shadow")} == {"MKT-S"}
    assert {p["market_ticker"] for p in ledger.open_decisions("live")} == {"MKT-L"}
    ledger.close()


def test_live_bankroll_never_falls_back_to_shadow_fiction(tmp_path):
    """Balance-fetch failure in LIVE must not size risk off the fake $100."""
    import json as _json

    from autonomy.brain import SHADOW_BANKROLL_CENTS, PredatorBrain
    from autonomy.executor import Executor
    from autonomy.learner import Learner
    from autonomy.ontology import SessionMode
    from autonomy.reconciler import Reconciler
    from autonomy.risk_brain import RiskBrain
    from autonomy.scanner import MarketScanner

    ledger = AutonomyLedger(tmp_path / "l.db")

    def boom():
        raise RuntimeError("network")

    risk_path = tmp_path / "risk_live.json"
    brain = PredatorBrain(
        mode=SessionMode.LIVE, ledger=ledger, registry=None,
        scanner=MarketScanner(fetch_series=lambda s: {"markets": []}, watchlist=[]),
        risk_brain=RiskBrain(state_path=risk_path),
        executor=Executor(SessionMode.SHADOW, session_path=tmp_path / "s.json",
                          kill_path=tmp_path / "KILL"),
        reconciler=Reconciler(ledger, fetch_market_result=lambda t: {}),
        learner=Learner(ledger), balance_fn=boom)

    # No persisted state -> zero budget, never the shadow constant.
    assert brain._bankroll_cents() == 0
    # With a last-known live bankroll on file -> use it.
    risk_path.write_text(_json.dumps({"bankroll_cents": 2941}), encoding="utf-8")
    assert brain._bankroll_cents() == 2941
    assert brain._bankroll_cents() != SHADOW_BANKROLL_CENTS
    ledger.close()


# ---------------------------------------------------------------- recalibration


def test_daemon_recalibration_gates(tmp_path, monkeypatch):
    import autonomy.daemon as daemon

    # Env gate off -> no-op.
    monkeypatch.setenv("DUMMY_DAEMON_RECAL", "0")
    assert daemon._maybe_recalibrate(NOW.isoformat()) is None

    # Fresh stamp -> short-circuits before touching the ledger.
    monkeypatch.setenv("DUMMY_DAEMON_RECAL", "1")
    monkeypatch.setattr(daemon, "RECAL_STAMP_PATH", tmp_path / "stamp.json")
    (tmp_path / "stamp.json").write_text(
        f'{{"at": "{NOW.isoformat()}"}}', encoding="utf-8")
    assert daemon._maybe_recalibrate(NOW.isoformat()) is None
