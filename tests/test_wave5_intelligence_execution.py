"""Wave-5: execution-policy env selection + taker path, sports calibration bar,
weather challenger retirement, runtime env whitelist."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone


from autonomy.execution_policy import ENV_EXECUTION_POLICY_VAR, ExecutionPolicy
from autonomy.executor import Executor
from autonomy.ontology import (
    Decision,
    DecisionAction,
    Forecast,
    MarketView,
    OutcomeKind,
    SessionMode,
    Vertical,
)


def _decision(price=40, count=2, side="yes", p_yes=0.80):
    forecast = Forecast(
        market_ticker="KXBTC-26JUL17-B64000", probability_yes=p_yes, uncertainty=0.1,
        sources_used={}, market_implied_yes=0.5, edge_yes=p_yes - 0.5, rationale="",
    )
    return Decision(
        decision_id="d-taker-1", market_ticker="KXBTC-26JUL17-B64000",
        action=DecisionAction.BUY_YES, side=side, price_cents=price, count=count,
        ev_cents_per_contract=10.0, kelly_fraction=0.05, notional_cents=price * count,
        forecast=forecast, risk_snapshot={},
    )


def _market() -> MarketView:
    return MarketView(
        ticker="KXBTC-26JUL17-B64000",
        title="BTC test",
        vertical=Vertical.CRYPTO,
        status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        yes_bid=40,
        yes_ask=45,
        no_bid=55,
        no_ask=60,
        volume=100,
        liquidity=100,
        raw={"category": "Crypto"},
    )


# ---- ExecutionPolicy.from_env -------------------------------------------------

def test_from_env_defaults_to_control(monkeypatch):
    monkeypatch.delenv(ENV_EXECUTION_POLICY_VAR, raising=False)
    assert ExecutionPolicy.from_env().is_control()


def test_from_env_selects_supported_cohorts(monkeypatch):
    monkeypatch.setenv(ENV_EXECUTION_POLICY_VAR, "C1")
    policy = ExecutionPolicy.from_env()
    assert policy.cohort == "C1" and policy.mode == "taker"
    monkeypatch.setenv(ENV_EXECUTION_POLICY_VAR, "c3")
    assert ExecutionPolicy.from_env().cohort == "C3"


def test_from_env_fails_closed_on_unsupported(monkeypatch):
    for raw in ("C2", "C4", "banana"):
        monkeypatch.setenv(ENV_EXECUTION_POLICY_VAR, raw)
        assert ExecutionPolicy.from_env().is_control()


# ---- taker path in the executor (shadow book) ---------------------------------

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_taker_reprices_shadow_order_to_the_ask():
    executor = Executor(
        SessionMode.SHADOW,
        quote_fn=lambda ticker: {
            "yes_ask": 45,
            "yes_bid": 40,
            "no_ask": 60,
            "no_bid": 55,
            "yes_ask_levels": [[45, 10]],
            "book_received_at": datetime.now(timezone.utc).isoformat(),
        },
        execution_policy=ExecutionPolicy.taker_only(taker_min_ev_cents=3.0),
    )
    outcome = _run(
        executor.execute(_decision(price=40, p_yes=0.80), market=_market())
    )
    assert outcome.kind is OutcomeKind.SHADOW
    assert outcome.fill_price_cents == 45          # crossed the ask, not the maker 40
    assert "taker" in outcome.detail["note"]


def test_taker_blocks_when_ev_below_min():
    executor = Executor(
        SessionMode.SHADOW,
        quote_fn=lambda ticker: {
            "yes_ask": 79,
            "yes_bid": 74,
            "yes_ask_levels": [[79, 10]],
            "book_received_at": datetime.now(timezone.utc).isoformat(),
        },
        execution_policy=ExecutionPolicy.taker_only(taker_min_ev_cents=3.0),
    )
    # p=0.80 vs ask 79: EV ~= 80 - 79 - fee < 3c minimum -> refuse to cross.
    outcome = _run(
        executor.execute(_decision(price=70, p_yes=0.80), market=_market())
    )
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.detail["reason"] == "taker_ev_below_min"


def test_taker_blocks_without_fresh_book():
    executor = Executor(
        SessionMode.SHADOW,
        quote_fn=None,
        execution_policy=ExecutionPolicy.taker_only(),
    )
    outcome = _run(executor.execute(_decision(), market=_market()))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.detail["reason"] == "taker_no_fresh_book"


def test_control_policy_path_unchanged_maker():
    executor = Executor(
        SessionMode.SHADOW,
        quote_fn=lambda ticker: {"yes_ask": 45, "yes_bid": 40},
        execution_policy=ExecutionPolicy.maker_only_control(),
    )
    outcome = _run(
        executor.execute(_decision(price=40, p_yes=0.80), market=_market())
    )
    assert outcome.kind is OutcomeKind.SHADOW
    assert outcome.fill_price_cents == 40          # resting maker price, untouched
    assert "maker" in outcome.detail["note"]


# ---- shadow taker via the PUBLIC quote path (latent-bug regression) -----------
# The audit bug: quote_fn was wired only for LIVE sessions, so every shadow C1
# order died "taker_no_fresh_book" and paper evidence could never accrue under
# the taker policy. These tests pin (a) the session wiring for BOTH books and
# (b) the executor evaluating the taker path through the real public read-only
# quote reader (fresh_best_quote over an injected unauthenticated book fetch),
# including its fail-closed fetch-failure and staleness behavior.

def _public_book_quote_fn(fetch_orderbook):
    """The real public quote path with only the raw book fetch injected."""
    from autonomy.live_book import fresh_best_quote

    return lambda ticker: fresh_best_quote(ticker, fetch_orderbook=fetch_orderbook)


def test_shadow_and_live_sessions_both_wire_public_fresh_quote_reader(
    tmp_path, monkeypatch
):
    from autonomy import session as session_mod
    from autonomy.live_book import fresh_best_quote
    from core import state as core_state

    # No creds/global-mode side effects: this test asserts wiring only.
    monkeypatch.setattr(session_mod, "_ensure_creds_loaded", lambda: None)
    monkeypatch.setattr(core_state.STATE, "set_mode", lambda _mode: None)
    for mode in (SessionMode.SHADOW, SessionMode.LIVE):
        brain = session_mod.build_brain(
            mode,
            ledger_path=tmp_path / f"wiring-{mode.value}.db",
            source_health_path=tmp_path / f"health-{mode.value}.json",
        )
        try:
            assert brain.executor.quote_fn is fresh_best_quote, mode
        finally:
            brain.ledger.close()


def test_taker_evaluates_in_shadow_via_public_quote_path():
    # Public REST book schema: yes/no bid ladders; YES ask = 100 - best NO bid.
    quote_fn = _public_book_quote_fn(
        lambda ticker: {"yes": [[40, 100]], "no": [[55, 50]]}
    )
    executor = Executor(
        SessionMode.SHADOW,
        quote_fn=quote_fn,
        execution_policy=ExecutionPolicy.taker_only(taker_min_ev_cents=3.0),
    )
    outcome = _run(
        executor.execute(_decision(price=40, p_yes=0.80), market=_market())
    )
    assert outcome.kind is OutcomeKind.SHADOW
    assert outcome.fill_price_cents == 45          # crossed 100-55, not maker 40
    assert "taker" in outcome.detail["note"]
    assert outcome.detail["liquidity_role"] == "taker"


def test_taker_blocks_in_shadow_when_public_quote_fetch_fails():
    def boom(_ticker):
        raise RuntimeError("public book unreachable")

    executor = Executor(
        SessionMode.SHADOW,
        quote_fn=_public_book_quote_fn(boom),
        execution_policy=ExecutionPolicy.taker_only(),
    )
    outcome = _run(executor.execute(_decision(), market=_market()))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.detail["reason"] == "taker_no_fresh_book"


def test_taker_blocks_in_shadow_when_public_quote_is_stale():
    quote_fn = _public_book_quote_fn(
        lambda ticker: {"yes": [[40, 100]], "no": [[55, 50]]}
    )
    executor = Executor(
        SessionMode.SHADOW,
        quote_fn=quote_fn,
        execution_policy=ExecutionPolicy.taker_only(),
        # The executor's clock sits far past the quote's receipt witness, so
        # the freshness gate must refuse rather than fabricate a fresh book.
        now_fn=lambda: datetime.now(timezone.utc).timestamp() + 120.0,
    )
    outcome = _run(executor.execute(_decision(), market=_market()))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.detail["reason"] == "taker_quote_stale"


# ---- sports reliability bar ---------------------------------------------------

def test_sports_scope_fits_at_lower_cluster_bar():
    from autonomy.reliability import (
        SPORTS_MIN_CALIBRATION_CLUSTERS,
        fit_maps_from_rows,
    )

    class _Row:
        def __init__(self, i, source, scope):
            self.source = source
            self.ticker = f"T-{i}"
            self.event_cluster = f"E{i}"
            self.probability_yes = 0.9 if i % 2 else 0.6
            # STRONG miscalibration spread evenly across i (0.9 realizes 30%,
            # 0.6 realizes 60% in every stretch of ten): Wave-18's validation
            # gate holds out ~20% of clusters and refuses maps that do not
            # improve there, so the fixture's correction must be large enough
            # to survive any holdout draw -- this test pins the CLUSTER BAR,
            # not the validation margin.
            self.result_yes = (i // 2) % 10 < (3 if i % 2 else 6)
            self.features = {}
            self.scope = scope

    n = SPORTS_MIN_CALIBRATION_CLUSTERS + 20   # 80: above sports bar, below crypto's 200
    sports_rows = [_Row(i, "mlb_total_runs", "mlb_total_runs|mlb|total_runs|pre") for i in range(n)]
    crypto_rows = [_Row(i, "crypto_spot_vol", "crypto_spot_vol|btc|ladder|hourly") for i in range(n)]
    maps = fit_maps_from_rows(sports_rows + crypto_rows)
    assert "mlb_total_runs|mlb|total_runs|pre" in maps          # sports bar: fits at 80
    assert "crypto_spot_vol|btc|ladder|hourly" not in maps      # crypto bar: still needs 200


# ---- weather retirement -------------------------------------------------------

def test_weather_signal_is_data_only_and_has_no_prediction_authority():
    import inspect

    from autonomy.signals import weather_openmeteo

    src = inspect.getsource(weather_openmeteo)
    assert "data_only = True" in src
    assert "prediction_authority = False" in src
    assert "def applicable" in src and "return False" in src


# ---- runtime env whitelist ----------------------------------------------------

def test_runtime_env_refs_whitelisted():
    from core.env_loader import ALLOWED_ENV_REFS

    assert "DUMMY_DEBATE_LIVE" in ALLOWED_ENV_REFS
    assert "DUMMY_EXECUTION_POLICY" in ALLOWED_ENV_REFS


# ---- routing config sanity ----------------------------------------------------

def test_every_role_routes_to_directed_models():
    import json
    from pathlib import Path

    config = json.loads(Path("configs/model_routing.json").read_text())
    panel = [
        "gpt_5_6_terra",
        "gpt_5_6_luna",
        "claude_sonnet_5",
        "glm_5_2",
    ]
    allowed = {*panel, "hybrid"}
    for role, provider in config["default_provider"].items():
        assert provider in allowed, f"{role} routed to {provider}"
    assert config["hybrid_providers"] == panel
    assert {
        name: config["provider_configs"][name]["model_name"] for name in panel
    } == {
        "gpt_5_6_terra": "openai/gpt-5.6-terra",
        "gpt_5_6_luna": "openai/gpt-5.6-luna",
        "claude_sonnet_5": "anthropic/claude-sonnet-5",
        "glm_5_2": "z-ai/glm-5.2",
    }
    assert config["default_provider"] == {
        "forecast_opinion": "gpt_5_6_terra",
        "rapid_forecast": "gpt_5_6_luna",
        "strategy_critique": "claude_sonnet_5",
        "risk_critique": "glm_5_2",
        "no_trade_reason": "glm_5_2",
        "trade_draft": "gpt_5_6_luna",
        "calibration_note": "glm_5_2",
        "market_thesis": "claude_sonnet_5",
        "reflection_lessons": "claude_sonnet_5",
        "hybrid_review": "hybrid",
    }
    assert config["live_model_calls_enabled"] is False
