"""Risk brain: Kelly, fees, stage budgets, drawdown ladder, self-promotion."""

from __future__ import annotations

from autonomy.ontology import Stage
from autonomy.risk_brain import (
    DRAWDOWN_LADDER,
    PROMOTION_MIN_SETTLED,
    RiskBrain,
    RiskState,
    kalshi_taker_fee_cents,
    kelly_fraction_yes,
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
