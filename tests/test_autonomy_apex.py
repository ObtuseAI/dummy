"""Tests: sportsbook consensus + steam, crypto challenger, per-vertical trust,
tape reader, capital-velocity ranking, circuit breakers, self-recalibration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    assert _american("EVEN") == 100
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
    client = EspnClient(fetch_scoreboard=lambda l, d: scoreboard)
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
    source = SportsbookConsensusSignal(espn=EspnClient(fetch_scoreboard=lambda l, d: bare))
    assert source.generate(_market("KXMLBGAME-26JUL091910KCNYM-NYM")) is None
    # Started game -> stale line -> no opinion.
    started = {"events": [_event_with_ml("NYM", "KC", "-149", "+124", state="in")]}
    source2 = SportsbookConsensusSignal(espn=EspnClient(fetch_scoreboard=lambda l, d: started))
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
    ledger.close()


def test_backtest_bootstraps_scoped_weights(tmp_path):
    from autonomy.backtest import run_backtest

    ledger = AutonomyLedger(tmp_path / "l.db")
    for i, (ticker, result) in enumerate([("KXBTCD-A", True), ("KXBTCD-B", False),
                                          ("KXHIGHNY-C", True)]):
        ledger.record_signal(Signal(source="market_prior", market_ticker=ticker,
                                    probability_yes=0.5, uncertainty=0.1, rationale=""))
        ledger.record_signal(Signal(source="alpha", market_ticker=ticker,
                                    probability_yes=0.9 if result else 0.1,
                                    uncertainty=0.1, rationale=""))
        ledger.record_settlement(ticker, result)
    report = run_backtest(ledger, bootstrap_weights=True)
    assert "alpha@CRYPTO" in report["derived_weights_by_vertical"]
    assert "alpha@WEATHER" in report["derived_weights_by_vertical"]
    assert ledger.get_weight("alpha@CRYPTO", default=0.0) > 1.0
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
