"""Persistence and normalization regressions for audit Task 3."""

from __future__ import annotations

from core.kalshi_market_validator import validate_ticker_shape
from core.ontology import CapConfig, Position
from core.state import DummyState
from compliance.governor import assess_compliance
from live_firewall.exposure_tracker import ExposureTracker


def _position(market: str, contract: str, side: str, quantity: int = 1, price: int = 50) -> Position:
    return Position(
        market_ticker=market,
        contract_ticker=contract,
        side=side,
        quantity=quantity,
        avg_price_cents=price,
        unrealized_pnl_cents=0,
    )


def test_daily_realized_loss_persists_and_is_idempotent(tmp_path):
    path = tmp_path / "risk_state.json"
    state = DummyState(persist=True, state_path=path)

    assert state.record_realized_pnl(-125, settlement_id="decision-1") is True
    assert state.record_realized_pnl(-125, settlement_id="decision-1") is False
    state.record_realized_pnl(50, settlement_id="decision-2")

    reloaded = DummyState(persist=True, state_path=path)
    assert reloaded.daily_loss_cents == 125
    assert reloaded.record_realized_pnl(-25, settlement_id="decision-3") is True
    assert DummyState(persist=True, state_path=path).daily_loss_cents == 150


def test_corrupt_daily_loss_state_is_not_treated_as_zero(tmp_path):
    path = tmp_path / "risk_state.json"
    path.write_text("{", encoding="utf-8")

    state = DummyState(persist=True, state_path=path)

    assert state.persistence_error is not None


def test_exposure_persists_both_sides_without_overwrite(tmp_path):
    path = tmp_path / "exposure.json"
    tracker = ExposureTracker(persist=True, state_path=path)
    tracker.update_position(_position("KXBTC-EVENT", "KXBTC-EVENT", "yes", price=40))
    tracker.update_position(_position("KXBTC-EVENT", "KXBTC-EVENT", "no", price=60))
    tracker.add_open_order(
        "order-1", "KXBTC-EVENT", 1, 40,
        contract_ticker="KXBTC-EVENT", side="yes",
    )

    reloaded = ExposureTracker(persist=True, state_path=path)

    assert set(reloaded.positions) == {
        ("KXBTC-EVENT", "yes"),
        ("KXBTC-EVENT", "no"),
    }
    # Filled positions reserve 40c + 60c and the still-open YES order reserves
    # another 40c. Counting both prevents capital from being double-spent.
    assert reloaded.total_exposure_cents() == 140
    assert reloaded.open_order_count() == 1

    reloaded.remove_open_order("order-1")
    reloaded.remove_position("KXBTC-EVENT", "yes")
    final = ExposureTracker(persist=True, state_path=path)
    assert final.open_order_count() == 0
    assert set(final.positions) == {("KXBTC-EVENT", "no")}


def test_corrupt_exposure_state_fails_closed(tmp_path):
    path = tmp_path / "exposure.json"
    path.write_text("not-json", encoding="utf-8")

    tracker = ExposureTracker(persist=True, state_path=path)

    assert tracker.state_healthy is False


def test_blocked_category_matching_is_case_insensitive():
    caps = CapConfig(blocked_categories=["kxpolitics"])

    verdict = assess_compliance("KXPOLITICS-2028", "KXPOLITICS-2028", caps=caps)

    assert verdict.passed is False
    assert verdict.blocked_categories == ["kxpolitics"]


def test_validator_accepts_observed_real_kalshi_shapes():
    observed = [
        "KXBTC-26DEC25000-C",
        "KXMVESPORTSMULTIGAMEEXTENDED-S2026507888D9EE4-E8412AFB1D6",
        "INFX-26JUL-T116249.99",
    ]

    assert all(validate_ticker_shape(ticker).ok for ticker in observed)
    assert not validate_ticker_shape("WEATHER-NYC-RAIN").ok
    assert not validate_ticker_shape("KXBTC/../../SECRET").ok


def test_live_settlement_updates_persisted_daily_loss(tmp_path, monkeypatch):
    from autonomy.brain import PredatorBrain
    from autonomy.ontology import SessionMode, Stage
    from autonomy.risk_brain import RiskState
    from core import state as state_module
    from live_firewall import exposure_tracker as exposure_module

    class Ledger:
        def __init__(self):
            self.outcomes = []

        def record_outcome(self, outcome):
            self.outcomes.append(outcome)

    risk_path = tmp_path / "risk_state.json"
    exposure_path = tmp_path / "exposure_state.json"
    monkeypatch.setenv("DUMMY_EXPOSURE_STATE_PATH", str(exposure_path))
    monkeypatch.setattr(exposure_module, "_PERSISTENT_TRACKER", None)
    live_state = DummyState(persist=True, state_path=risk_path)
    monkeypatch.setattr(state_module, "STATE", live_state)

    brain = object.__new__(PredatorBrain)
    brain.mode = SessionMode.LIVE
    brain.ledger = Ledger()
    state = RiskState(
        bankroll_cents=1000,
        equity_peak_cents=1000,
        stage=Stage.CANARY,
        open_exposure_cents=60,
        open_markets=1,
        daily_pnl_cents=0,
        settled_count_at_stage=0,
        realized_pnl_per_contract_cents=0.0,
    )
    decision = {
        "decision_id": "live-decision-1",
        "market_ticker": "KXBTC-LOSS",
        "side": "YES",
        "price_cents": 60,
        "count": 1,
        "filled_count": 1,
        "order_id": "order-1",
    }

    brain._close_position(state, decision, result_yes=False)

    assert brain.ledger.outcomes[-1].pnl_cents < 0
    assert live_state.daily_loss_cents == -brain.ledger.outcomes[-1].pnl_cents
    assert DummyState(persist=True, state_path=risk_path).daily_loss_cents == live_state.daily_loss_cents
