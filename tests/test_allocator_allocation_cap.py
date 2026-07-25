"""The allocation cap is an additional upper bound on an already-approved size.

The cross-candidate allocator may grant a candidate less than its own caps
would allow, so that a top-ranked market cannot drain the whole cycle pot.
The cap must only ever REDUCE -- every existing risk-brain and firewall bound
still binds afterwards.
"""
from __future__ import annotations

import inspect

from autonomy.allocator import Allocator
from autonomy.ontology import DecisionAction
from autonomy.risk_brain import RiskBrain

from tests.test_autonomy_pipeline import _forecast, _market


def _setup(tmp_path):
    brain = RiskBrain(state_path=tmp_path / "risk.json")
    state = brain.load_state(100_000)
    market = _market(ticker="KXBTCD-26JUL10-T100000.00", yes_bid=30, yes_ask=40)
    return Allocator(brain), market, _forecast(market, 0.65), state


class TestSignature:
    def test_decide_accepts_an_allocation_cap(self):
        sig = inspect.signature(Allocator.decide)
        assert "allocation_cap_cents" in sig.parameters
        assert sig.parameters["allocation_cap_cents"].default is None

    def test_allocation_cap_is_keyword_only(self):
        sig = inspect.signature(Allocator.decide)
        kind = sig.parameters["allocation_cap_cents"].kind
        assert kind is inspect.Parameter.KEYWORD_ONLY


class TestBehaviour:
    def test_baseline_trades_without_a_cap(self, tmp_path):
        allocator, market, forecast, state = _setup(tmp_path)
        decision = allocator.decide(market, forecast, state)
        assert decision.action is DecisionAction.BUY_YES
        assert decision.count > 0

    def test_cap_reduces_count_but_never_raises_it(self, tmp_path):
        allocator, market, forecast, state = _setup(tmp_path)
        uncapped = allocator.decide(market, forecast, state)
        capped = allocator.decide(
            market, forecast, state,
            allocation_cap_cents=uncapped.notional_cents // 2)
        assert capped.count <= uncapped.count
        assert capped.notional_cents <= uncapped.notional_cents

    def test_cap_above_the_budget_changes_nothing(self, tmp_path):
        allocator, market, forecast, state = _setup(tmp_path)
        uncapped = allocator.decide(market, forecast, state)
        generous = allocator.decide(
            market, forecast, state, allocation_cap_cents=10_000_000)
        assert generous.count == uncapped.count
        assert generous.notional_cents == uncapped.notional_cents

    def test_zero_cap_abstains(self, tmp_path):
        allocator, market, forecast, state = _setup(tmp_path)
        decision = allocator.decide(market, forecast, state, allocation_cap_cents=0)
        assert decision.action is DecisionAction.ABSTAIN
        assert decision.count == 0

    def test_negative_cap_abstains(self, tmp_path):
        allocator, market, forecast, state = _setup(tmp_path)
        decision = allocator.decide(market, forecast, state, allocation_cap_cents=-500)
        assert decision.action is DecisionAction.ABSTAIN
        assert decision.count == 0

    def test_abstain_reason_names_the_allocation(self, tmp_path):
        allocator, market, forecast, state = _setup(tmp_path)
        decision = allocator.decide(market, forecast, state, allocation_cap_cents=0)
        assert "allocation" in (decision.abstain_reason or "")

    def test_none_cap_is_identical_to_omitting_it(self, tmp_path):
        allocator, market, forecast, state = _setup(tmp_path)
        omitted = allocator.decide(market, forecast, state)
        explicit = allocator.decide(market, forecast, state, allocation_cap_cents=None)
        assert explicit.count == omitted.count
        assert explicit.notional_cents == omitted.notional_cents
