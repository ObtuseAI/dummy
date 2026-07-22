"""Partial fills reserve actual fills plus worst-case remaining LIMIT cost."""
from __future__ import annotations

from autonomy.brain import PredatorBrain, _reserved_exposure_cents
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import (
    Decision,
    DecisionAction,
    Forecast,
    OutcomeKind,
    TradeOutcome,
)


TICKER = "KXMLBGAME-26JUL21-ABC"


def _decision() -> Decision:
    forecast = Forecast(
        market_ticker=TICKER,
        probability_yes=0.80,
        uncertainty=0.10,
        sources_used={"model": 1.0},
        market_implied_yes=0.50,
        edge_yes=0.30,
        rationale="partial reserve test",
    )
    return Decision(
        decision_id="partial-reserve",
        market_ticker=TICKER,
        action=DecisionAction.BUY_YES,
        side="yes",
        price_cents=52,
        count=4,
        ev_cents_per_contract=20.0,
        kelly_fraction=0.10,
        notional_cents=208,
        forecast=forecast,
        risk_snapshot={},
    )


def _outcome(kind: OutcomeKind, fill_count: int, *, fill_cost: int | None):
    detail = {
        "submitted_price_cents": 52,
        "submitted_count": 4,
        "submitted_notional_cents": 208,
        "liquidity_role": "taker",
    }
    if fill_cost is not None:
        detail["fill_cost_cents"] = fill_cost
    return TradeOutcome(
        decision_id="partial-reserve",
        market_ticker=TICKER,
        kind=kind,
        order_id="order-1",
        fill_count=fill_count,
        fill_price_cents=50 if fill_count else 52,
        pnl_cents=None,
        broker_contacted=True,
        detail=detail,
    )


def test_active_partial_fill_reserves_fill_cost_plus_unfilled_limit(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(_decision())
        ledger.record_outcome(_outcome(OutcomeKind.ACCEPTED, 0, fill_cost=None))
        ledger.record_outcome(_outcome(OutcomeKind.PARTIALLY_FILLED, 1, fill_cost=50))

        position = ledger.open_decisions("live")[0]
        assert position["fill_price_cents"] == 50
        assert position["filled_count"] == 1
        assert position["reserved_count"] == 4
        # One witnessed 50c fill + three unfilled contracts at the 52c LIMIT.
        assert position["reserved_notional_cents"] == 50 + 3 * 52 == 206
        assert _reserved_exposure_cents(position) == 206

        brain = object.__new__(PredatorBrain)
        brain.ledger = ledger
        brain.book_scope = "live"
        assert brain._market_exposure(None, TICKER) == 206
        assert brain._group_exposure(TICKER)[0] == 206
    finally:
        ledger.close()


def test_terminal_partial_fill_releases_unfilled_remainder(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(_decision())
        ledger.record_outcome(_outcome(OutcomeKind.ACCEPTED, 0, fill_cost=None))
        ledger.record_outcome(_outcome(OutcomeKind.PARTIALLY_FILLED, 1, fill_cost=50))
        ledger.record_outcome(_outcome(OutcomeKind.CANCELED, 1, fill_cost=50))

        position = ledger.open_decisions("live")[0]
        assert position["order_active"] == 0
        assert position["reserved_count"] == 1
        assert position["reserved_notional_cents"] == 50
    finally:
        ledger.close()


def test_reserved_exposure_falls_back_for_legacy_rows():
    assert _reserved_exposure_cents({
        "price_cents": 47,
        "count": 3,
        "reserved_count": 2,
    }) == 94
