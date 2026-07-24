"""End-to-end autonomy pipeline tests with injected fetchers — no network."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.allocator import Allocator
from autonomy.executor import AUTONOMY_ACK, SESSION_ACCOUNTING_VERSION, Executor
from autonomy.execution_policy import ExecutionPolicy
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
from autonomy.scanner import MarketScanner, classify_vertical, to_market_view
from autonomy.signals.base import SourceRegistry
from autonomy.signals.crypto_spot import CryptoSpotVolSignal
from autonomy.signals.market_prior import MarketPriorSignal
from autonomy.signals.weather_openmeteo import OpenMeteoWeatherSignal, parse_temp_ticker


def _market(ticker="KXELONMARS-26JUL10", yes_bid=30, yes_ask=40, volume=500, **overrides) -> MarketView:
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
    # WNBA / NCAAF / NCAAMB must classify as SPORTS -- KXWNBA* never matched the
    # KXNBA prefix and KXNCAA* matched nothing, so they used to fall to OTHER and
    # were dropped by the scan-time {CRYPTO, SPORTS} gate (never traded/listed).
    assert classify_vertical("KXWNBAGAME-26JUL19LVLA-LV") is Vertical.SPORTS
    assert classify_vertical("KXNCAAFGAME-26SEP13TEXOU-TEX") is Vertical.SPORTS
    assert classify_vertical("KXNCAAMBGAME-26NOV20DUKEUNC-DUKE") is Vertical.SPORTS
    assert classify_vertical("KXWHATEVER-1") is Vertical.OTHER


def test_never_built_sports_prefixes_do_not_classify_as_tradeable():
    """Tennis and esports must fall to OTHER, not SPORTS.

    KXWTA / KXATP / KXESPORTS were mapped to Vertical.SPORTS but never appeared
    in WATCHLIST_SERIES, so no pricing path was ever built for them (0 signals
    and 0 decisions on the live ledger). That combination is a latent hazard
    rather than merely dead code: the retired commodities/econ prefixes are
    safe to keep because they classify into verticals the scan-time
    {CRYPTO, SPORTS} gate EXCLUDES, whereas these classified into SPORTS, which
    the gate ADMITS. A tennis market reaching the scanner by any route would
    have been handed to a sports pipeline with nothing behind it.

    KXMVESPORTS is deliberately NOT in this list: the multi-game parlay series
    is real, carries real historical second-proof evidence, and is asserted
    above.
    """
    for ticker in (
        "KXWTAMATCH-26JUL20-SWI",
        "KXATPMATCH-26JUL20-ALC",
        "KXESPORTSLOL-26JUL20-T1",
    ):
        assert classify_vertical(ticker) is Vertical.OTHER, ticker
    # The MVE parlay series is real evidence and must keep classifying SPORTS.
    assert classify_vertical("KXMVESPORTSMULTIGAMEEXTENDED-X-Y") is Vertical.SPORTS


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
    # Weather (KXHIGHNY) is no longer traded by default; only KXETH (crypto) is scanned.
    assert tickers == ["KXETH-26JUL10-T4000"]
    assert calls == ["KXHIGHNY", "KXETH", "KXDEAD"]
    eth = views[0]
    assert eth.yes_bid == 30 and eth.yes_ask == 40  # dollars-string schema normalized
    assert eth.volume == 12


def test_scanner_treats_zero_and_one_dollar_quotes_as_missing_sentinels():
    view = to_market_view({
        "ticker": "KXBTC-26JUL10-B65000", "status": "active",
        "yes_bid_dollars": "0.0000", "yes_ask_dollars": "0.7600",
        "no_bid_dollars": "0.2400", "no_ask_dollars": "1.0000",
    })
    assert view.yes_bid is None and view.no_ask is None
    assert view.yes_ask == 76 and view.no_bid == 24


def test_scanner_preserves_current_quote_size_fp_schema_when_liquidity_is_zero():
    view = to_market_view({
        "ticker": "KXMLBGAME-26JUL221840MINCLE-CLE",
        "status": "active",
        "yes_bid_dollars": "0.5600",
        "yes_ask_dollars": "0.5700",
        "no_bid_dollars": "0.4300",
        "no_ask_dollars": "0.4400",
        "yes_bid_size_fp": "145999.74",
        "yes_ask_size_fp": "471822.17",
        "liquidity_dollars": "0.0000",
    })

    assert view.liquidity == 0
    assert view.raw["yes_bid_size_fp"] == "145999.74"
    assert view.raw["yes_ask_size_fp"] == "471822.17"


def test_scanner_classifies_exact_added_crypto_and_commodity_series():
    assert classify_vertical("KXSOL15M-26JUL100430-30") is Vertical.CRYPTO
    assert classify_vertical("BTCD-26JUL10-T70000") is Vertical.CRYPTO
    assert classify_vertical("KXNATGASW-26JUL1017-T4.899") is Vertical.COMMODITIES
    assert classify_vertical("KXDOGE15M-26JUL100430-30") is Vertical.OTHER
    assert classify_vertical("KXXRP15M-26JUL100430-30") is Vertical.OTHER


def test_scanner_no_longer_trades_weather_by_default():
    from autonomy.scanner import MarketScanner
    from autonomy.ontology import Vertical
    scanner = MarketScanner(fetch_series=lambda s: {"markets": []})
    assert Vertical.WEATHER not in scanner.verticals
    # The other verticals remain tradable.
    assert Vertical.SPORTS in scanner.verticals
    assert Vertical.CRYPTO in scanner.verticals


def test_scanner_excludes_weather_market_when_scanned():
    from autonomy.scanner import MarketScanner
    from autonomy.ontology import Vertical
    weather_page = {"markets": [{
        "ticker": "KXHIGHNY-26JUL11-T85", "status": "active",
        "yes_bid": 40, "yes_ask": 42, "no_bid": 58, "no_ask": 60,
    }]}
    scanner = MarketScanner(
        fetch_series=lambda s: weather_page, watchlist=["KXHIGHNY"],
    )
    views = scanner.scan()
    # A weather market still classifies as WEATHER but is filtered out of the scan.
    assert all(v.vertical is not Vertical.WEATHER for v in views)


def test_scanner_quarantines_equity_even_with_custom_other_vertical():
    from autonomy.ontology import Vertical
    from autonomy.scanner import MarketScanner

    page = {"markets": [{
        "ticker": "KXTSLAA-26JUL22-B350",
        "status": "active",
        "category": "Equities",
        "yes_bid": 40,
        "yes_ask": 42,
        "no_bid": 58,
        "no_ask": 60,
    }]}
    scanner = MarketScanner(
        fetch_series=lambda _series: page,
        watchlist=["KXTSLAA"],
        verticals={Vertical.OTHER},
    )

    assert scanner.scan() == []


@pytest.mark.parametrize(
    ("series", "ticker"),
    [
        ("KXBAA", "KXBAA-28JANDELIV-700"),
        ("KXEBAYA", "KXEBAYA-28JANGMV-92000000000.0"),
        ("KXCVNAA", "KXCVNAA-28JANUNITS-910000"),
        ("KXFA", "KXFA-28JANUSSALES-2300000.0"),
        ("KXUALA", "KXUALA-28JANPAX-190000000"),
    ],
)
def test_scanner_quarantines_current_company_kpi_market_shapes(series, ticker):
    """Market-list payloads omit series category, so exact series guards apply."""
    page = {"markets": [{
        "ticker": ticker,
        "event_ticker": ticker.rsplit("-", 1)[0],
        "status": "active",
        "yes_bid": 40,
        "yes_ask": 42,
        "no_bid": 58,
        "no_ask": 60,
    }]}
    scanner = MarketScanner(
        fetch_series=lambda _series: page,
        watchlist=[series],
        verticals={Vertical.OTHER},
    )

    assert scanner.scan() == []


def test_crypto_ticker_parse_hour_glued():
    from autonomy.signals.crypto_spot import parse_crypto_ticker

    parsed = parse_crypto_ticker("KXBTCD-26JUL0917-T71249.99")
    assert parsed == {
        "asset": "BTC", "strike": 71249.99, "contract_family": "ladder",
    }
    assert parse_crypto_ticker("KXSOL15M-26JUL100415-15") == {
        "asset": "SOL", "strike": 0.0, "contract_family": "15m_direction",
    }


# ---------------------------------------------------------------- signals


def test_weather_ticker_parse():
    parsed = parse_temp_ticker("KXHIGHNY-26JUL10-T85")
    assert parsed == {"kind": "HIGH", "city": "NY", "date_iso": "2026-07-10", "style": "T", "threshold": 85.0}
    assert parse_temp_ticker("KXHIGHZZZ-26JUL10-T85") is None


def test_weather_signal_is_retired_data_only():
    hot = OpenMeteoWeatherSignal(fetch_daily_temps=lambda *a: [90.0, 91.0, 89.5])
    market = _market()
    assert hot.data_only is True
    assert hot.prediction_authority is False
    assert hot.applicable(market) is False
    assert hot.generate(market) is None


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


def test_weather_contract_never_emits_forecast():
    source = OpenMeteoWeatherSignal(fetch_daily_temps=lambda *a: [90.0, 91.0, 89.5])
    market = _market(ticker="KXHIGHNY-26JUL10-T83",
                     raw={"strike_type": "less", "cap_strike": 83.0})
    assert source.generate(market) is None


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


def test_forecaster_keeps_minimum_market_anchor_against_overconfident_model(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    try:
        ledger.update_weight("model", 8.0)
        ledger.update_weight("market_prior", 3.0)
        market = _market(yes_bid=39, yes_ask=41, volume=1)
        forecast = EnsembleForecaster(ledger).fuse(market, [
            Signal("market_prior", market.ticker, 0.40, 0.50, ""),
            Signal("model", market.ticker, 0.90, 0.01, ""),
        ])
        assert forecast.sources_used["market_prior"] == 0.05
        assert forecast.probability_yes == pytest.approx(0.875)
    finally:
        ledger.close()


def test_crypto_fused_uncertainty_cannot_collapse_below_floor(tmp_path):
    """Two agreeing high-trust crypto vol models must not manufacture ~2%
    fused uncertainty; the crypto floor (0.08) holds where the per-signal
    floor otherwise leaks away in inverse-variance fusion."""
    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    try:
        ledger.update_weight("crypto_spot_vol", 8.0)
        ledger.update_weight("crypto_ewma_t", 8.0)
        ledger.update_weight("market_prior", 3.0)
        market = _market(
            ticker="KXBTCD-26JUL11-T63799.99", yes_bid=74, yes_ask=76, volume=1,
        )
        assert market.vertical is Vertical.CRYPTO
        forecast = EnsembleForecaster(ledger).fuse(market, [
            Signal("crypto_spot_vol", market.ticker, 0.70, 0.08, ""),
            Signal("crypto_ewma_t", market.ticker, 0.71, 0.08, ""),
            Signal("market_prior", market.ticker, 0.75, 0.20, ""),
        ])
        assert forecast.uncertainty >= 0.08 - 1e-9
    finally:
        ledger.close()


def test_non_crypto_fused_uncertainty_keeps_global_floor(tmp_path):
    """The crypto floor is vertical-scoped for an allowed generic market."""
    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    try:
        ledger.update_weight("weather_openmeteo", 8.0)
        ledger.update_weight("market_prior", 3.0)
        market = _market(ticker="KXELONMARS-26JUL11", yes_bid=39, yes_ask=41)
        assert market.vertical is not Vertical.CRYPTO
        forecast = EnsembleForecaster(ledger).fuse(market, [
            Signal("weather_openmeteo", market.ticker, 0.70, 0.08, ""),
            Signal("market_prior", market.ticker, 0.72, 0.20, ""),
        ])
        assert forecast.uncertainty < 0.08
        assert forecast.uncertainty >= 0.02 - 1e-9
    finally:
        ledger.close()


def test_ensemble_rejects_weather_prediction_target(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    try:
        market = _market(ticker="KXHIGHNY-26JUL11-T85", yes_bid=39, yes_ask=41)
        assert EnsembleForecaster(ledger).fuse(market, [
            Signal("weather_openmeteo", market.ticker, 0.70, 0.08, ""),
        ]) is None
    finally:
        ledger.close()


# ---------------------------------------------------------------- allocator


def _forecast(market, probability, uncertainty=0.08):
    ledger_signals = [Signal(source="s", market_ticker=market.ticker,
                             probability_yes=probability, uncertainty=uncertainty, rationale="")]
    class _FakeLedger:
        def get_weight(self, source, default=1.0):
            return 1.0

    return EnsembleForecaster(_FakeLedger()).fuse(market, ledger_signals)


def test_allocator_buys_yes_on_positive_edge(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(
        ticker="KXBTCD-26JUL10-T100000.00", yes_bid=30, yes_ask=40
    )
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


def test_taker_allocator_prices_entry_at_executable_ask(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(yes_bid=30, yes_ask=45)
    decision = Allocator(
        brain, execution_policy=ExecutionPolicy.taker_only(),
    ).decide(market, _forecast(market, 0.80), state)
    assert decision.action is DecisionAction.BUY_YES
    assert decision.price_cents == 45


def test_taker_allocator_rejects_phantom_maker_edge(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(yes_bid=34, yes_ask=54)
    decision = Allocator(
        brain, execution_policy=ExecutionPolicy.taker_only(),
    ).decide(market, _forecast(market, 0.55), state)
    assert decision.action is DecisionAction.ABSTAIN
    assert decision.price_cents == 54
    assert "below taker threshold" in decision.abstain_reason


def test_allocator_abstains_on_high_uncertainty(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market()
    decision = Allocator(brain).decide(market, _forecast(market, 0.9, uncertainty=0.45), state)
    assert decision.action is DecisionAction.ABSTAIN
    assert "uncertainty" in decision.abstain_reason


def test_allocator_rejects_wide_or_one_sided_books(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    wide = _market(yes_bid=1, yes_ask=80)
    decision = Allocator(brain).decide(wide, _forecast(wide, 0.95), state)
    assert decision.action is DecisionAction.ABSTAIN
    assert "spread" in decision.abstain_reason
    one_sided = _market(yes_bid=None, yes_ask=80, no_bid=20, no_ask=None)
    decision = Allocator(brain).decide(one_sided, _forecast(one_sided, 0.95), state)
    assert decision.action is DecisionAction.ABSTAIN
    assert "two-sided" in decision.abstain_reason


def test_allocator_never_forces_one_contract_above_remaining_budget(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(10_000)
    market = _market(yes_bid=80, yes_ask=90)
    decision = Allocator(brain).decide(
        market, _forecast(market, 0.99), state,
        market_exposure_cents=0, group_exposure_cents=0,
        group_open_count=0,
    )
    assert decision.action is DecisionAction.ABSTAIN
    assert "below one contract" in decision.abstain_reason


def test_allocator_fails_closed_on_missing_close_time_at_canary(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(yes_bid=30, yes_ask=40, close_time="")
    decision = Allocator(brain).decide(market, _forecast(market, 0.80), state)
    assert decision.action is DecisionAction.ABSTAIN
    assert "invalid close time" in decision.abstain_reason


# ---------------------------------------------------------------- executor


def test_executor_shadow_never_contacts_broker(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(
        ticker="KXBTCD-26JUL10-T100000.00", yes_bid=30, yes_ask=40
    )
    decision = Allocator(brain).decide(market, _forecast(market, 0.7), state)
    executor = Executor(SessionMode.SHADOW, session_path=tmp_path / "s.json", kill_path=tmp_path / "KILL")
    outcome = asyncio.run(executor.execute(decision, market=market))
    assert outcome.kind is OutcomeKind.SHADOW
    assert outcome.broker_contacted is False


def test_executor_shadow_captures_fixed_point_queue_ahead(tmp_path):
    market = _market(
        ticker="KXBTCD-26JUL10-T100000.00", yes_bid=30, yes_ask=50
    )
    decision = _forecast(market, 0.70)
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    allocated = Allocator(brain).decide(
        market, decision, brain.load_state(100_000)
    )
    executor = Executor(
        SessionMode.SHADOW,
        shadow_book_fn=lambda _ticker: {
            "yes_dollars": [[f"{allocated.price_cents / 100:.4f}", "7.25"]],
            "no_dollars": [],
        },
    )
    outcome = asyncio.run(executor.execute(allocated, market=market))
    assert outcome.detail["queue_snapshot_available"] is True
    assert outcome.detail["queue_ahead_contracts"] == 7.25


def test_executor_shadow_blocks_unexecutable_queue(tmp_path):
    market = _market(
        ticker="KXBTCD-26JUL10-T100000.00", yes_bid=30, yes_ask=50
    )
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    allocated = Allocator(brain).decide(
        market, _forecast(market, 0.70), brain.load_state(100_000),
    )
    outcome = asyncio.run(Executor(
        SessionMode.SHADOW,
        shadow_book_fn=lambda _ticker: {
            "yes_dollars": [[f"{allocated.price_cents / 100:.4f}", "500.00"]],
            "no_dollars": [],
        },
    ).execute(allocated, market=market))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.detail["reason"] == "queue_ahead_exceeds_execution_cap"


def test_executor_live_blocked_without_session(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(
        ticker="KXBTCD-26JUL10-T100000.00", yes_bid=30, yes_ask=40
    )
    decision = Allocator(brain).decide(market, _forecast(market, 0.7), state)
    executor = Executor(SessionMode.LIVE, session_path=tmp_path / "missing.json", kill_path=tmp_path / "KILL")
    outcome = asyncio.run(executor.execute(decision, market=market))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.broker_contacted is False


def _write_live_session(path, ack=AUTONOMY_ACK, hours=1.0):
    payload = {
        "mode": "LIVE",
        "ack": ack,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(),
        "accounting_version": SESSION_ACCOUNTING_VERSION,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_executor_live_blocked_on_kill_switch(tmp_path):
    session = tmp_path / "s.json"
    _write_live_session(session)
    kill = tmp_path / "KILL"
    kill.write_text("x", encoding="utf-8")
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(
        ticker="KXBTCD-26JUL10-T100000.00", yes_bid=30, yes_ask=40
    )
    decision = Allocator(brain).decide(market, _forecast(market, 0.7), state)
    executor = Executor(SessionMode.LIVE, session_path=session, kill_path=kill)
    outcome = asyncio.run(executor.execute(decision, market=market))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL


def test_executor_live_accept_and_reject_witness(tmp_path, monkeypatch):
    session = tmp_path / "s.json"
    _write_live_session(session)
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    brain.save_state(state)
    market = _market(
        ticker="KXBTCD-26JUL10-T100000.00", yes_bid=30, yes_ask=40
    )
    decision = Allocator(brain).decide(market, _forecast(market, 0.7), state)

    class FakeClient:
        async def get_orderbook(self, ticker, depth=10):
            from core.ontology import OrderBook, OrderBookLevel

            return OrderBook(
                market_ticker=ticker,
                contract_ticker=ticker,
                bids=[OrderBookLevel(price=30, size=10)],
                asks=[OrderBookLevel(price=40, size=10)],
                timestamp=datetime.now(timezone.utc),
            )

        async def close(self):
            pass

    class FakeFirewall:
        def __init__(self, result):
            self._result = result
            self.client = FakeClient()

        def live_authority_verdict(self):
            from core.ontology import FirewallVerdict

            return FirewallVerdict(allow=True, reason="test authority")

        async def submit(self, request, orderbook, forecast):
            return self._result

    from core.ontology import LiveOrderResult

    accepted = LiveOrderResult(
        success=True, order_id="ord-1", proof_reference="sp", broker_contacted=True
    )
    executor = Executor(
        SessionMode.LIVE,
        session_path=session,
        kill_path=tmp_path / "KILL",
        risk_state_path=brain.state_path,
        exchange_status_fn=lambda: {"exchange_active": True, "trading_active": True},
    )
    monkeypatch.setattr(executor, "_make_firewall", lambda: FakeFirewall(accepted))
    outcome = asyncio.run(executor.execute(decision, market=market))
    assert outcome.kind is OutcomeKind.ACCEPTED
    assert outcome.broker_contacted is True

    rejected = LiveOrderResult(
        success=False, error="BROKER_VALIDATION", proof_reference="sp", broker_contacted=True
    )
    executor2 = Executor(
        SessionMode.LIVE, session_path=session, kill_path=tmp_path / "KILL",
        risk_state_path=brain.state_path,
        exchange_status_fn=lambda: {"exchange_active": True, "trading_active": True},
    )
    monkeypatch.setattr(executor2, "_make_firewall", lambda: FakeFirewall(rejected))
    outcome2 = asyncio.run(executor2.execute(decision, market=market))
    assert outcome2.kind is OutcomeKind.REJECTED
    assert outcome2.broker_contacted is True

    local = LiveOrderResult(
        success=False, error="KILL_SWITCH_ACTIVE", proof_reference="sp", broker_contacted=False
    )
    executor3 = Executor(
        SessionMode.LIVE, session_path=session, kill_path=tmp_path / "KILL",
        risk_state_path=brain.state_path,
        exchange_status_fn=lambda: {"exchange_active": True, "trading_active": True},
    )
    monkeypatch.setattr(executor3, "_make_firewall", lambda: FakeFirewall(local))
    outcome3 = asyncio.run(executor3.execute(decision, market=market))
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
    # Isolate from any cwd-relative runtime/no_edge_map.json: the fusion floor is
    # tested on its own; here the strong crypto signal must drive an order
    # regardless of whatever scopes live evidence has floored.
    monkeypatch.setattr("autonomy.no_edge_map.load_negative_scopes", lambda *a, **k: frozenset())
    from autonomy.brain import PredatorBrain
    from autonomy.signals.crypto_spot import CryptoSpotVolSignal

    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    registry = SourceRegistry()
    registry.register(MarketPriorSignal())
    # Use crypto signal instead of weather signal (weather no longer traded by default)
    registry.register(CryptoSpotVolSignal(fetch_spot_and_vol=lambda asset: (100_000.0, 0.5)))

    def fetch_series(series):
        if series != "KXBTCD":
            return {"markets": []}
        return {"markets": [{
            "ticker": "KXBTCD-26JUL10-T100000.00",
            "title": "BTC spot above $100k",
            "status": "active",
            "close_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            "yes_bid": 30, "yes_ask": 40, "no_bid": 60, "no_ask": 70,
            "volume": 500, "liquidity": 1000,
            "strike_type": "greater", "floor_strike": 100000.0,
        }]}

    brain = PredatorBrain(
        mode=SessionMode.SHADOW,
        ledger=ledger,
        registry=registry,
        scanner=MarketScanner(fetch_series=fetch_series, watchlist=["KXBTCD"]),
        risk_brain=RiskBrain(state_path=tmp_path / "risk.json"),
        executor=Executor(SessionMode.SHADOW, session_path=tmp_path / "s.json", kill_path=tmp_path / "KILL"),
        reconciler=Reconciler(ledger, fetch_market_result=lambda t: {"result": ""}),
        learner=Learner(ledger),
        board_path=tmp_path / "bet_board.json",
    )
    try:
        report = asyncio.run(brain.run_cycle())
        assert report.status == "CYCLE_OK"
        assert report.markets_scanned == 1
        assert report.signals_generated >= 2
        assert report.decisions_made == 1
        assert report.orders_placed == 1  # strong crypto signal vs 35c mid = strong YES edge
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
