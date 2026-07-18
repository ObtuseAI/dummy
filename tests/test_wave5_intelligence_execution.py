"""Wave-5: execution-policy env selection + taker path, sports calibration bar,
weather challenger retirement, runtime env whitelist."""
from __future__ import annotations

import asyncio


from autonomy.execution_policy import ENV_EXECUTION_POLICY_VAR, ExecutionPolicy
from autonomy.executor import Executor
from autonomy.ontology import (
    Decision,
    DecisionAction,
    Forecast,
    OutcomeKind,
    SessionMode,
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
        quote_fn=lambda ticker: {"yes_ask": 45, "yes_bid": 40, "no_ask": 60, "no_bid": 55},
        execution_policy=ExecutionPolicy.taker_only(taker_min_ev_cents=3.0),
    )
    outcome = _run(executor.execute(_decision(price=40, p_yes=0.80)))
    assert outcome.kind is OutcomeKind.SHADOW
    assert outcome.fill_price_cents == 45          # crossed the ask, not the maker 40
    assert "taker" in outcome.detail["note"]


def test_taker_blocks_when_ev_below_min():
    executor = Executor(
        SessionMode.SHADOW,
        quote_fn=lambda ticker: {"yes_ask": 79, "yes_bid": 74},
        execution_policy=ExecutionPolicy.taker_only(taker_min_ev_cents=3.0),
    )
    # p=0.80 vs ask 79: EV ~= 80 - 79 - fee < 3c minimum -> refuse to cross.
    outcome = _run(executor.execute(_decision(price=70, p_yes=0.80)))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.detail["reason"] == "taker_ev_below_min"


def test_taker_blocks_without_fresh_book():
    executor = Executor(
        SessionMode.SHADOW,
        quote_fn=None,
        execution_policy=ExecutionPolicy.taker_only(),
    )
    outcome = _run(executor.execute(_decision()))
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.detail["reason"] == "taker_no_fresh_book"


def test_control_policy_path_unchanged_maker():
    executor = Executor(
        SessionMode.SHADOW,
        quote_fn=lambda ticker: {"yes_ask": 45, "yes_bid": 40},
        execution_policy=ExecutionPolicy.maker_only_control(),
    )
    outcome = _run(executor.execute(_decision(price=40, p_yes=0.80)))
    assert outcome.kind is OutcomeKind.SHADOW
    assert outcome.fill_price_cents == 40          # resting maker price, untouched
    assert "maker" in outcome.detail["note"]


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
            # Miscalibration spread EVENLY across i (win rates 90%/70% in
            # every stretch of ten) so any held-out cluster subset realizes
            # ~the true rate -- Wave-18's validation gate holds out ~20% of
            # clusters and refuses maps that do not improve there, which a
            # block-pattern fixture (all wins first, all losses after) fails
            # for reasons that have nothing to do with the cluster bar this
            # test pins.
            self.result_yes = (i // 2) % 10 < (9 if i % 2 else 7)
            self.features = {}
            self.scope = scope

    n = SPORTS_MIN_CALIBRATION_CLUSTERS + 20   # 80: above sports bar, below crypto's 200
    sports_rows = [_Row(i, "mlb_total_runs", "mlb_total_runs|mlb|total_runs|pre") for i in range(n)]
    crypto_rows = [_Row(i, "crypto_spot_vol", "crypto_spot_vol|btc|ladder|hourly") for i in range(n)]
    maps = fit_maps_from_rows(sports_rows + crypto_rows)
    assert "mlb_total_runs|mlb|total_runs|pre" in maps          # sports bar: fits at 80
    assert "crypto_spot_vol|btc|ladder|hourly" not in maps      # crypto bar: still needs 200


# ---- weather retirement -------------------------------------------------------

def test_weather_emits_challenger_only():
    import inspect

    from autonomy.signals import weather_openmeteo

    src = inspect.getsource(weather_openmeteo)
    assert '"challenger_only": True' in src


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
    allowed = {"glm_5_2", "minimax_m3", "hybrid"}
    for role, provider in config["default_provider"].items():
        assert provider in allowed, f"{role} routed to {provider}"
    assert config["provider_configs"]["glm_5_2"]["model_name"] == "z-ai/glm-5.2"
    assert config["provider_configs"]["minimax_m3"]["model_name"] == "minimax/minimax-m3"
