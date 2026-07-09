"""End-to-end autonomy pipeline tests with injected fetchers — no network."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.allocator import Allocator
from autonomy.executor import AUTONOMY_ACK, Executor
from autonomy.forecaster import EnsembleForecaster
from autonomy.learner import Learner
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import (
    DecisionAction,
    MarketView,
    OutcomeKind,
    SessionMode,
    Signal,
    Vertical,
)
from autonomy.reconciler import Reconciler, settlement_pnl_cents
from autonomy.risk_brain import RiskBrain
from autonomy.scanner import MarketScanner, classify_vertical
from autonomy.signals.base import SourceRegistry
from autonomy.signals.crypto_spot import CryptoSpotVolSignal
from autonomy.signals.market_prior import MarketPriorSignal
from autonomy.signals.weather_openmeteo import OpenMeteoWeatherSignal, parse_temp_ticker


def _market(ticker="KXHIGHNY-26JUL10-T85", yes_bid=30, yes_ask=40, volume=500, **overrides) -> MarketView:
    defaults = dict(
        ticker=ticker,
        title="test market",
        vertical=classify_vertical(ticker),
        status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=100 - yes_ask if yes_ask else None,
        no_ask=100 - yes_bid if yes_bid else None,
        volume=volume,
        liquidity=1000,
    )
    defaults.update(overrides)
    return MarketView(**defaults)


# ---------------------------------------------------------------- scanner


def test_classify_verticals():
    assert classify_vertical("KXHIGHNY-26JUL10-T85") is Vertical.WEATHER
    assert classify_vertical("KXBTCD-26JUL08H17-T107999.99") is Vertical.CRYPTO
    assert classify_vertical("KXMVESPORTSMULTIGAMEEXTENDED-X-Y") is Vertical.SPORTS
    assert classify_vertical("KXWHATEVER-1") is Vertical.OTHER


def test_scanner_walks_watchlist_and_filters():
    by_series = {
        "KXHIGHNY": {"markets": [
            {"ticker": "KXHIGHNY-26JUL10-T85", "status": "active", "volume": 10},
            {"ticker": "KXHIGHNY-26JUL10-T90", "status": "closed"},
        ]},
        "KXETH": {"markets": [
            {"ticker": "KXETH-26JUL10-T4000", "status": "active",
             "yes_bid_dollars": "0.3000", "yes_ask_dollars": "0.4000", "volume_fp": "12.00"},
        ]},
    }
    calls = []

    def fetch(series):
        calls.append(series)
        return by_series.get(series, {"markets": []})

    views = MarketScanner(fetch_series=fetch, watchlist=["KXHIGHNY", "KXETH", "KXDEAD"]).scan()
    tickers = [v.ticker for v in views]
    assert tickers == ["KXHIGHNY-26JUL10-T85", "KXETH-26JUL10-T4000"]
    assert calls == ["KXHIGHNY", "KXETH", "KXDEAD"]
    eth = views[1]
    assert eth.yes_bid == 30 and eth.yes_ask == 40  # dollars-string schema normalized
    assert eth.volume == 12


def test_crypto_ticker_parse_hour_glued():
    from autonomy.signals.crypto_spot import parse_crypto_ticker

    parsed = parse_crypto_ticker("KXBTCD-26JUL0917-T71249.99")
    assert parsed == {"asset": "BTC", "strike": 71249.99}


# ---------------------------------------------------------------- signals


def test_weather_ticker_parse():
    parsed = parse_temp_ticker("KXHIGHNY-26JUL10-T85")
    assert parsed == {"kind": "HIGH", "city": "NY", "date_iso": "2026-07-10", "style": "T", "threshold": 85.0}
    assert parse_temp_ticker("KXHIGHZZZ-26JUL10-T85") is None


def test_weather_signal_probability_direction():
    hot = OpenMeteoWeatherSignal(fetch_daily_temps=lambda *a: [90.0, 91.0, 89.5])
    cold = OpenMeteoWeatherSignal(fetch_daily_temps=lambda *a: [70.0, 71.0, 69.5])
    market = _market()
    hot_signal = hot.generate(market)
    cold_signal = cold.generate(market)
    assert hot_signal.probability_yes > 0.8
    assert cold_signal.probability_yes < 0.2
    assert hot_signal.source == "weather_openmeteo"


def test_crypto_signal_above_below_strike():
    signal_source = CryptoSpotVolSignal(fetch_spot_and_vol=lambda asset: (110_000.0, 0.5))
    market = _market(ticker="KXBTCD-26JUL0817-T100000.00",
                     close_time=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                     raw={"strike_type": "greater", "floor_strike": 100000.0})
    result = signal_source.generate(market)
    assert result is not None
    assert result.probability_yes > 0.9  # spot 10% above strike, 2h horizon

    below = CryptoSpotVolSignal(fetch_spot_and_vol=lambda asset: (90_000.0, 0.5))
    below._cache = {}
    result2 = below.generate(market)
    assert result2.probability_yes < 0.1


def test_crypto_between_bucket_far_from_spot_is_near_zero():
    source = CryptoSpotVolSignal(fetch_spot_and_vol=lambda asset: (3_600.0, 0.6))
    market = _market(ticker="KXETH-26JUL0819-B1600",
                     close_time=(datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
                     raw={"strike_type": "between", "floor_strike": 1600.0, "cap_strike": 1619.99})
    result = source.generate(market)
    assert result is not None
    assert result.probability_yes <= 0.01  # dead bucket, not 0.99


def test_weather_less_strike_type_respected():
    source = OpenMeteoWeatherSignal(fetch_daily_temps=lambda *a: [90.0, 91.0, 89.5])
    market = _market(ticker="KXHIGHNY-26JUL10-T83",
                     raw={"strike_type": "less", "cap_strike": 83.0})
    result = source.generate(market)
    assert result.probability_yes < 0.02  # forecast ~90, "below 83" nearly impossible


def test_market_prior_thin_book_is_weak_anchor():
    thick = MarketPriorSignal().generate(_market(volume=5000))
    thin = MarketPriorSignal().generate(_market(volume=3))
    assert thin.uncertainty > thick.uncertainty


def test_registry_swallows_source_exceptions():
    class Boom:
        name = "boom"

        def applicable(self, market):
            return True

        def generate(self, market):
            raise RuntimeError("no")

    registry = SourceRegistry()
    registry.register(Boom())
    registry.register(MarketPriorSignal())
    signals = list(registry.signals_for(_market()))
    assert [s.source for s in signals] == ["market_prior"]


# ---------------------------------------------------------------- forecaster


def test_forecaster_weights_by_trust_and_uncertainty(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    try:
        ledger.update_weight("sharp", 4.0)
        ledger.update_weight("dull", 0.2)
        market = _market()
        signals = [
            Signal(source="sharp", market_ticker=market.ticker, probability_yes=0.8, uncertainty=0.05, rationale=""),
            Signal(source="dull", market_ticker=market.ticker, probability_yes=0.2, uncertainty=0.05, rationale=""),
        ]
        forecast = EnsembleForecaster(ledger).fuse(market, signals)
        assert forecast.probability_yes > 0.7  # pulled toward the trusted source
        assert forecast.market_implied_yes == pytest.approx(0.35)
        assert set(forecast.sources_used) == {"sharp", "dull"}
    finally:
        ledger.close()


# ---------------------------------------------------------------- allocator


def _forecast(market, probability, uncertainty=0.08):
    ledger_signals = [Signal(source="s", market_ticker=market.ticker,
                             probability_yes=probability, uncertainty=uncertainty, rationale="")]
    import sqlite3

    class _FakeLedger:
        def get_weight(self, source, default=1.0):
            return 1.0

    return EnsembleForecaster(_FakeLedger()).fuse(market, ledger_signals)


def test_allocator_buys_yes_on_positive_edge(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(yes_bid=30, yes_ask=40)
    decision = Allocator(brain).decide(market, _forecast(market, 0.65), state)
    assert decision.action is DecisionAction.BUY_YES
    assert 1 <= decision.price_cents <= 64  # below fair, maker-side
    assert decision.notional_cents <= 100  # canary cap


def test_allocator_buys_no_when_forecast_below_market(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(yes_bid=60, yes_ask=70)
    decision = Allocator(brain).decide(market, _forecast(market, 0.30), state)
    assert decision.action is DecisionAction.BUY_NO
    assert decision.side == "no"


def test_allocator_abstains_without_edge(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(yes_bid=49, yes_ask=51)
    decision = Allocator(brain).decide(market, _forecast(market, 0.50), state)
    assert decision.action is DecisionAction.ABSTAIN


def test_allocator_abstains_on_high_uncertainty(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market()
    decision = Allocator(brain).decide(market, _forecast(market, 0.9, uncertainty=0.45), state)
    assert decision.action is DecisionAction.ABSTAIN
    assert "uncertainty" in decision.abstain_reason


# ---------------------------------------------------------------- executor


def test_executor_shadow_never_contacts_broker(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(yes_bid=30, yes_ask=40)
    decision = Allocator(brain).decide(market, _forecast(market, 0.7), state)
    executor = Executor(SessionMode.SHADOW, session_path=tmp_path / "s.json", kill_path=tmp_path / "KILL")
    outcome = asyncio.run(executor.execute(decision))
    assert outcome.kind is OutcomeKind.SHADOW
    assert outcome.broker_contacted is False


def test_executor_live_blocked_without_session(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(yes_bid=30, yes_ask=40)
    decision = Allocator(brain).decide(market, _forecast(market, 0.7), state)
    executor = Executor(SessionMode.LIVE, session_path=tmp_path / "missing.json", kill_path=tmp_path / "KILL")
    outcome = asyncio.run(executor.execute(decision))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.broker_contacted is False


def _write_live_session(path, ack=AUTONOMY_ACK, hours=1.0):
    payload = {
        "mode": "LIVE",
        "ack": ack,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_executor_live_blocked_on_kill_switch(tmp_path):
    session = tmp_path / "s.json"
    _write_live_session(session)
    kill = tmp_path / "KILL"
    kill.write_text("x", encoding="utf-8")
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(yes_bid=30, yes_ask=40)
    decision = Allocator(brain).decide(market, _forecast(market, 0.7), state)
    executor = Executor(SessionMode.LIVE, session_path=session, kill_path=kill)
    outcome = asyncio.run(executor.execute(decision))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL


def test_executor_live_accept_and_reject_witness(tmp_path):
    session = tmp_path / "s.json"
    _write_live_session(session)
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(yes_bid=30, yes_ask=40)
    decision = Allocator(brain).decide(market, _forecast(market, 0.7), state)

    class FakeAdapter:
        def __init__(self, result):
            self._result = result

        async def submit_limit_order(self, request):
            return self._result

        async def close(self):
            pass

    from predator_mesh.brokers.livebrokerfirewall_adapter import SubmitResult

    accepted = SubmitResult(submitted=True, order_id="ord-1", state="OPEN", raw={}, errors=[])
    executor = Executor(SessionMode.LIVE, session_path=session, kill_path=tmp_path / "KILL",
                        adapter_factory=lambda d: FakeAdapter(accepted))
    outcome = asyncio.run(executor.execute(decision))
    assert outcome.kind is OutcomeKind.ACCEPTED
    assert outcome.broker_contacted is True

    rejected = SubmitResult(submitted=False, order_id=None, state="REJECTED",
                            raw={"status_code": 400, "stage": "broker_transport"}, errors=["BROKER_VALIDATION"])
    executor2 = Executor(SessionMode.LIVE, session_path=session, kill_path=tmp_path / "KILL",
                         adapter_factory=lambda d: FakeAdapter(rejected))
    outcome2 = asyncio.run(executor2.execute(decision))
    assert outcome2.kind is OutcomeKind.REJECTED
    assert outcome2.broker_contacted is True

    local = SubmitResult(submitted=False, order_id=None, state="REJECTED", raw={}, errors=["KILL_SWITCH_ACTIVE"])
    executor3 = Executor(SessionMode.LIVE, session_path=session, kill_path=tmp_path / "KILL",
                         adapter_factory=lambda d: FakeAdapter(local))
    outcome3 = asyncio.run(executor3.execute(decision))
    assert outcome3.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome3.broker_contacted is False


# ---------------------------------------------------------------- learner


def test_learner_rewards_market_beaters(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    try:
        ledger.record_signal(Signal(source="market_prior", market_ticker="T", probability_yes=0.5,
                                    uncertainty=0.1, rationale=""))
        ledger.record_signal(Signal(source="sharp", market_ticker="T", probability_yes=0.9,
                                    uncertainty=0.1, rationale=""))
        ledger.record_signal(Signal(source="dull", market_ticker="T", probability_yes=0.1,
                                    uncertainty=0.1, rationale=""))
        updated = Learner(ledger).apply_settlement("T", result_yes=True)
        assert updated["sharp"] > 1.0
        assert updated["dull"] < 1.0
    finally:
        ledger.close()


def test_settlement_pnl_math():
    assert settlement_pnl_cents("yes", 40, 1, result_yes=True) == 60 - 2  # fee 2c at p=40
    assert settlement_pnl_cents("yes", 40, 1, result_yes=False) == -40 - 2
    assert settlement_pnl_cents("no", 40, 1, result_yes=False) == 60 - 2


# ---------------------------------------------------------------- reconciler


def test_reconciler_detects_settlements(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    try:
        from autonomy.ontology import Decision, Forecast

        forecast = Forecast(market_ticker="T", probability_yes=0.7, uncertainty=0.1,
                            sources_used={}, market_implied_yes=0.5, edge_yes=0.2, rationale="")
        ledger.record_decision(Decision(
            decision_id="d1", market_ticker="T", action=DecisionAction.BUY_YES, side="yes",
            price_cents=40, count=1, ev_cents_per_contract=10.0, kelly_fraction=0.1,
            notional_cents=40, forecast=forecast, risk_snapshot={},
        ))
        reconciler = Reconciler(ledger, fetch_market_result=lambda t: {"result": "yes"})
        settled = reconciler.reconcile_settlements()
        assert settled == [("T", True)]
        # Idempotent: second pass finds nothing unsettled.
        assert reconciler.reconcile_settlements() == []
    finally:
        ledger.close()


# ---------------------------------------------------------------- full cycle


def test_full_shadow_cycle_places_shadow_orders(tmp_path, monkeypatch):
    from autonomy.brain import PredatorBrain

    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    registry = SourceRegistry()
    registry.register(MarketPriorSignal())
    registry.register(OpenMeteoWeatherSignal(fetch_daily_temps=lambda *a: [92.0, 93.0, 91.0]))

    def fetch_series(series):
        if series != "KXHIGHNY":
            return {"markets": []}
        return {"markets": [{
            "ticker": "KXHIGHNY-26JUL10-T85",
            "title": "NYC high temp above 85",
            "status": "active",
            "close_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "yes_bid": 30, "yes_ask": 40, "no_bid": 60, "no_ask": 70,
            "volume": 500, "liquidity": 1000,
        }]}

    brain = PredatorBrain(
        mode=SessionMode.SHADOW,
        ledger=ledger,
        registry=registry,
        scanner=MarketScanner(fetch_series=fetch_series, watchlist=["KXHIGHNY"]),
        risk_brain=RiskBrain(state_path=tmp_path / "risk.json"),
        executor=Executor(SessionMode.SHADOW, session_path=tmp_path / "s.json", kill_path=tmp_path / "KILL"),
        reconciler=Reconciler(ledger, fetch_market_result=lambda t: {"result": ""}),
        learner=Learner(ledger),
    )
    try:
        report = asyncio.run(brain.run_cycle())
        assert report.status == "CYCLE_OK"
        assert report.markets_scanned == 1
        assert report.signals_generated >= 2
        assert report.decisions_made == 1
        assert report.orders_placed == 1  # hot forecast vs 35c mid = strong YES edge
        summary = ledger.performance_summary()
        assert summary["decisions_total"] == 1
    finally:
        ledger.close()


def test_cycle_halts_on_kill_switch(tmp_path):
    from autonomy.brain import PredatorBrain

    kill = tmp_path / "KILL"
    kill.write_text("x", encoding="utf-8")
    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    try:
        brain = PredatorBrain(
            mode=SessionMode.SHADOW,
            ledger=ledger,
            registry=SourceRegistry(),
            scanner=MarketScanner(fetch_series=lambda s: {"markets": []}, watchlist=["KXHIGHNY"]),
            risk_brain=RiskBrain(state_path=tmp_path / "risk.json"),
            executor=Executor(SessionMode.SHADOW, session_path=tmp_path / "s.json", kill_path=kill),
            reconciler=Reconciler(ledger, fetch_market_result=lambda t: {}),
            learner=Learner(ledger),
        )
        report = asyncio.run(brain.run_cycle())
        assert report.status == "HALTED_KILL_SWITCH"
    finally:
        ledger.close()
