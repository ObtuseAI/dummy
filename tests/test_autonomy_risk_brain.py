"""Risk brain: Kelly, fees, stage budgets, drawdown ladder, self-promotion."""

from __future__ import annotations

import asyncio
import os

import pytest

from autonomy.brain import PredatorBrain
from autonomy.ontology import Stage
from autonomy.ontology import SessionMode
from autonomy.risk_brain import (
    DRAWDOWN_LADDER,
    PROMOTION_MIN_SETTLED,
    RiskBrain,
    RiskState,
    RiskStatePersistenceError,
    kalshi_taker_fee_cents,
    kelly_fraction_yes,
    uncertainty_adjusted_kelly,
)


def _state(tmp_path, bankroll=100_000, **overrides) -> tuple[RiskBrain, RiskState]:
    brain = RiskBrain(state_path=tmp_path / "risk_state.json")
    state = brain.load_state(bankroll)
    for key, value in overrides.items():
        setattr(state, key, value)
    return brain, state


def test_kelly_zero_when_no_edge():
    assert kelly_fraction_yes(0.40, 50) == 0.0
    assert kelly_fraction_yes(0.50, 50) == 0.0


def test_kelly_positive_and_bounded():
    k = kelly_fraction_yes(0.60, 50)
    assert 0.0 < k <= 1.0
    assert abs(k - (10.0 / 50.0)) < 1e-9  # (60-50)/(100-50)


def test_uncertainty_adjusted_kelly_is_monotone_and_fails_closed():
    certain = uncertainty_adjusted_kelly(0.65, 0.0, 50)
    uncertain = uncertainty_adjusted_kelly(0.65, 0.20, 50)
    too_uncertain = uncertainty_adjusted_kelly(0.65, float("nan"), 50)
    assert 0.0 < uncertain < certain
    assert too_uncertain == 0.0


def test_fee_formula_matches_kalshi_shape():
    # 7% * p*(1-p) per contract, ceil in cents: p=0.5 -> 1.75 -> 2 cents
    assert kalshi_taker_fee_cents(50, 1) == 2
    assert kalshi_taker_fee_cents(1, 1) == 1  # ceil of 0.0693
    assert kalshi_taker_fee_cents(50, 10) == 18  # ceil(17.5)


def test_default_state_starts_canary(tmp_path):
    _, state = _state(tmp_path)
    assert state.stage is Stage.CANARY


def test_order_budget_respects_stage_absolute_cap(tmp_path):
    brain, state = _state(tmp_path, bankroll=10_000_000)  # $100k so fractions don't bind
    budget = brain.order_budget(state, "T", 0, kelly=1.0)
    assert budget.allowed
    assert budget.max_notional_cents <= 100  # CANARY absolute cap


def test_order_budget_blocked_when_hard_stopped(tmp_path):
    brain, state = _state(tmp_path, hard_stopped=True, stop_reason="test")
    budget = brain.order_budget(state, "T", 0, kelly=1.0)
    assert not budget.allowed


def test_drawdown_half_sizing(tmp_path):
    brain, state = _state(tmp_path, bankroll=90_000)
    state.equity_peak_cents = 100_000
    assert brain.sizing_multiplier(state) == DRAWDOWN_LADDER[0][1]


def test_drawdown_hard_stop(tmp_path):
    brain, state = _state(tmp_path, bankroll=69_000)
    state.equity_peak_cents = 100_000
    state = brain.apply_drawdown_policy(state)
    assert state.hard_stopped


def test_drawdown_demotes_stage(tmp_path):
    brain, state = _state(tmp_path, bankroll=79_000)
    state.equity_peak_cents = 100_000
    state.stage = Stage.RAMP
    state = brain.apply_drawdown_policy(state)
    assert state.stage is Stage.CANARY
    assert state.last_demotion_at is not None


def test_promotion_requires_evidence(tmp_path):
    brain, state = _state(tmp_path)
    state.settled_count_at_stage = PROMOTION_MIN_SETTLED - 1
    state.realized_pnl_per_contract_cents = 5.0
    state = brain.maybe_promote(state)
    assert state.stage is Stage.CANARY  # not enough settlements

    state.settled_count_at_stage = PROMOTION_MIN_SETTLED
    state.realized_pnl_per_contract_cents = -1.0
    state = brain.maybe_promote(state)
    assert state.stage is Stage.CANARY  # negative realized edge

    state.realized_pnl_per_contract_cents = 5.0
    state = brain.maybe_promote(state)
    assert state.stage is Stage.RAMP  # earned


def test_promotion_blocked_during_cooloff(tmp_path):
    from datetime import datetime, timezone

    brain, state = _state(tmp_path)
    state.settled_count_at_stage = PROMOTION_MIN_SETTLED
    state.realized_pnl_per_contract_cents = 5.0
    state.last_demotion_at = datetime.now(timezone.utc).isoformat()
    state = brain.maybe_promote(state)
    assert state.stage is Stage.CANARY


def test_state_roundtrip(tmp_path):
    brain, state = _state(tmp_path)
    state.stage = Stage.RAMP
    state.open_exposure_cents = 123
    brain.save_state(state)
    loaded = brain.load_state(bankroll_cents=55_555)
    assert loaded.stage is Stage.RAMP
    assert loaded.open_exposure_cents == 123
    assert loaded.bankroll_cents == 55_555
    assert loaded.equity_peak_cents >= 55_555 or loaded.equity_peak_cents >= 100_000


def test_corrupt_existing_state_is_shadow_only_hard_stop(tmp_path):
    path = tmp_path / "risk_state.json"
    path.write_text("{", encoding="utf-8")
    brain = RiskBrain(path)

    state = brain.load_state(25_000)

    assert state.stage is Stage.SHADOW_ONLY
    assert state.hard_stopped is True
    assert state.stop_reason == "risk state unavailable: JSONDecodeError"
    assert brain.persistence_error == "JSONDecodeError"
    assert brain.order_budget(state, "KXTEST", 0, kelly=1.0).allowed is False


def test_save_state_uses_atomic_sibling_replace(tmp_path, monkeypatch):
    brain, state = _state(tmp_path)
    real_replace = os.replace
    calls = []

    def traced_replace(source, target):
        calls.append((source, target))
        return real_replace(source, target)

    monkeypatch.setattr("autonomy.risk_brain.os.replace", traced_replace)
    brain.save_state(state)

    assert calls == [(brain.state_path.with_suffix(".json.tmp"), brain.state_path)]
    assert brain.state_path.exists()
    assert not brain.state_path.with_suffix(".json.tmp").exists()


def test_failed_atomic_replace_preserves_previous_state(tmp_path, monkeypatch):
    brain, state = _state(tmp_path)
    brain.save_state(state)
    previous = brain.state_path.read_text(encoding="utf-8")
    state.stage = Stage.RAMP

    def fail_replace(_source, _target):
        raise PermissionError("simulated persistence failure")

    monkeypatch.setattr("autonomy.risk_brain.os.replace", fail_replace)
    with pytest.raises(RiskStatePersistenceError, match="PermissionError"):
        brain.save_state(state)

    assert brain.state_path.read_text(encoding="utf-8") == previous
    assert brain.persistence_error == "PermissionError"
    assert not brain.state_path.with_suffix(".json.tmp").exists()


class _SpyExecutor:
    execution_policy = None

    def __init__(self, kill_path):
        self.kill_path = kill_path
        self.calls = 0

    async def execute(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("executor must not be reached")


def _minimal_brain(tmp_path, risk_brain, executor):
    return PredatorBrain(
        mode=SessionMode.SHADOW,
        ledger=object(),
        registry=object(),
        scanner=object(),
        risk_brain=risk_brain,
        executor=executor,
        reconciler=object(),
        learner=object(),
    )


def test_corrupt_state_halts_cycle_before_executor(tmp_path):
    path = tmp_path / "risk_state.json"
    path.write_text("not-json", encoding="utf-8")
    risk_brain = RiskBrain(path)
    executor = _SpyExecutor(tmp_path / "KILL")

    report = asyncio.run(_minimal_brain(tmp_path, risk_brain, executor).run_cycle())

    assert report.status == "HALTED_RISK_STATE_UNAVAILABLE"
    assert report.stage == int(Stage.SHADOW_ONLY)
    assert report.notes == ["risk_state_load_error=JSONDecodeError"]
    assert executor.calls == 0
    assert path.read_text(encoding="utf-8") == "not-json"


def test_unwritable_risk_sink_halts_before_executor(tmp_path, monkeypatch):
    from autonomy.switches import Switches

    monkeypatch.delenv("DUMMY_MAIN_ENABLED", raising=False)
    monkeypatch.setattr(
        Switches,
        "load",
        classmethod(lambda cls, path=None: cls({"main": True})),
    )
    risk_brain = RiskBrain(tmp_path / "risk_state.json")

    def fail_save(_state):
        raise RiskStatePersistenceError("risk state persistence failed: PermissionError")

    monkeypatch.setattr(risk_brain, "save_state", fail_save)
    executor = _SpyExecutor(tmp_path / "KILL")

    report = asyncio.run(_minimal_brain(tmp_path, risk_brain, executor).run_cycle())

    assert report.status == "HALTED_RISK_STATE_PERSISTENCE"
    assert report.notes == ["risk state persistence failed: PermissionError"]
    assert executor.calls == 0
