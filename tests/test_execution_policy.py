"""Tests for the typed ExecutionPolicy and its executor consumption (WS-A2/F2).

The load-bearing guarantee is that the maker-only control (C0) is a strict
no-op in the executor: default (no policy) and the explicit control policy must
produce byte-identical TradeOutcomes, so C0 reproduces current behavior. Only a
non-control policy consults the new guard hooks.
"""
from __future__ import annotations

import asyncio

import pytest

from autonomy.execution_policy import (
    COHORT_ORDER,
    ExecutionPolicy,
    default_cohorts,
)
from autonomy.executor import Executor
from autonomy.ontology import Decision, DecisionAction, Forecast, OutcomeKind, SessionMode


def _decision(price: int = 48, count: int = 2, forecast_p: float = 0.8) -> Decision:
    forecast = Forecast(
        market_ticker="KXBTC-26JUN01-A", probability_yes=forecast_p, uncertainty=0.1,
        sources_used={}, market_implied_yes=0.5, edge_yes=forecast_p - 0.5, rationale="",
    )
    return Decision(
        decision_id="d1", market_ticker="KXBTC-26JUN01-A", action=DecisionAction.BUY_YES,
        side="yes", price_cents=price, count=count, ev_cents_per_contract=5.0,
        kelly_fraction=0.1, notional_cents=price * count, forecast=forecast,
        risk_snapshot={},
    )


# --------------------------------------------------------------------------- #
# Policy object
# --------------------------------------------------------------------------- #


def test_control_is_control_and_serializes():
    control = ExecutionPolicy.maker_only_control()
    assert control.cohort == "C0"
    assert control.is_control()
    assert not control.takes_liquidity()
    payload = control.to_dict()
    assert payload["is_control"] is True
    assert payload["mode"] == "maker"


def test_default_cohorts_are_c0_through_c4_control_first():
    cohorts = default_cohorts()
    assert tuple(p.cohort for p in cohorts) == COHORT_ORDER
    assert cohorts[0].is_control()
    # Only the control is a control; the other four are challengers.
    assert sum(1 for p in cohorts if p.is_control()) == 1


def test_taker_and_hybrid_take_liquidity_but_guarded_maker_does_not():
    assert ExecutionPolicy.taker_only().takes_liquidity()
    assert ExecutionPolicy.taker_walk_forward().takes_liquidity()
    assert ExecutionPolicy.hybrid_patient_then_take().takes_liquidity()
    guarded = ExecutionPolicy.adverse_guard_maker()
    assert not guarded.takes_liquidity()
    assert not guarded.is_control()  # guards armed => not the control


def test_c3_carries_all_three_guards():
    c3 = ExecutionPolicy.adverse_guard_maker()
    assert c3.fast_cross_guard_seconds == 60.0
    assert c3.presubmit_book_recheck is True
    assert c3.divergence_cap_cents == 10.0


def test_walk_forward_threshold_is_marked_selected():
    c2 = ExecutionPolicy.taker_walk_forward().with_edge_threshold(7)
    assert c2.taker_min_edge_cents == 7.0
    assert c2.edge_threshold_walk_forward_selected is True


def test_invalid_mode_and_cohort_rejected():
    with pytest.raises(ValueError):
        ExecutionPolicy(cohort="C0", label="x", mode="nonsense")
    with pytest.raises(ValueError):
        ExecutionPolicy(cohort="ZZ", label="x", mode="maker")
    with pytest.raises(ValueError):
        ExecutionPolicy(cohort="C1", label="x", mode="taker", taker_min_edge_cents=-1)


# --------------------------------------------------------------------------- #
# Executor consumption: C0 reproduces current behavior exactly
# --------------------------------------------------------------------------- #


def test_executor_control_reproduces_default_behavior_exactly():
    decision = _decision()
    default = asyncio.run(Executor(SessionMode.SHADOW).execute(decision))
    control = asyncio.run(
        Executor(
            SessionMode.SHADOW, execution_policy=ExecutionPolicy.maker_only_control()
        ).execute(decision)
    )
    assert default.kind is control.kind
    assert default.fill_price_cents == control.fill_price_cents
    # Ignore the wall-clock TTL stamp, which differs only by submission instant.
    d_detail = {k: v for k, v in default.detail.items() if k != "expiration_ts"}
    c_detail = {k: v for k, v in control.detail.items() if k != "expiration_ts"}
    assert d_detail == c_detail


def test_executor_defaults_to_control_policy():
    executor = Executor(SessionMode.SHADOW)
    assert executor.execution_policy.is_control()


def test_c3_divergence_cap_blocks_wide_divergence():
    decision = _decision(forecast_p=0.8)  # model 0.80 vs prior 0.50 => 30c > 10c cap
    outcome = asyncio.run(
        Executor(
            SessionMode.SHADOW, execution_policy=ExecutionPolicy.adverse_guard_maker()
        ).execute(decision, market_prior_yes=0.5)
    )
    assert outcome.kind is OutcomeKind.BLOCKED_LOCAL
    assert outcome.detail["reason"] == "execution_policy_divergence_cap"
    assert outcome.detail["cohort"] == "C3"


def test_c3_divergence_cap_allows_narrow_divergence():
    decision = _decision(forecast_p=0.8)  # model 0.80 vs prior 0.75 => 5c <= 10c cap
    outcome = asyncio.run(
        Executor(
            SessionMode.SHADOW, execution_policy=ExecutionPolicy.adverse_guard_maker()
        ).execute(decision, market_prior_yes=0.75)
    )
    assert outcome.kind is OutcomeKind.SHADOW


def test_c3_fails_open_without_market_prior():
    # No prior => the divergence guard cannot evaluate; it must not refuse blind.
    decision = _decision(forecast_p=0.8)
    outcome = asyncio.run(
        Executor(
            SessionMode.SHADOW, execution_policy=ExecutionPolicy.adverse_guard_maker()
        ).execute(decision)
    )
    assert outcome.kind is OutcomeKind.SHADOW


def test_control_never_blocks_on_divergence():
    # The control policy ignores market prior entirely (no new branch).
    decision = _decision(forecast_p=0.99)
    outcome = asyncio.run(
        Executor(SessionMode.SHADOW).execute(decision, market_prior_yes=0.01)
    )
    assert outcome.kind is OutcomeKind.SHADOW
