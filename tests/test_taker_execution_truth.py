"""End-to-end regressions for submitted and witnessed execution truth."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.brain import PredatorBrain
from autonomy.execution_policy import ExecutionPolicy
from autonomy.executor import Executor
from autonomy.fees import kalshi_maker_fee_cents, kalshi_taker_fee_cents
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import (
    Decision,
    DecisionAction,
    Forecast,
    MarketView,
    OutcomeKind,
    SessionMode,
    Stage,
    TradeOutcome,
    Vertical,
)
from autonomy.reconciler import Reconciler, settlement_pnl_cents
from autonomy.risk_brain import RiskState, kelly_fraction_yes


TICKER = "KXMLBGAME-26JUL10-ABC"


def _decision(
    decision_id: str = "d-taker",
    *,
    price: int = 40,
    count: int = 3,
    conservative_p_side: float = 0.70,
) -> Decision:
    forecast = Forecast(
        market_ticker=TICKER,
        probability_yes=0.80,
        uncertainty=0.10,
        sources_used={"model": 1.0},
        market_implied_yes=0.40,
        edge_yes=0.40,
        rationale="execution truth test",
    )
    encoded_ev = (
        conservative_p_side * 100
        - price
        - kalshi_taker_fee_cents(price, 1, TICKER)
    )
    return Decision(
        decision_id=decision_id,
        market_ticker=TICKER,
        action=DecisionAction.BUY_YES,
        side="yes",
        price_cents=price,
        count=count,
        ev_cents_per_contract=encoded_ev,
        kelly_fraction=kelly_fraction_yes(conservative_p_side, price),
        notional_cents=price * count,
        forecast=forecast,
        risk_snapshot={"risk_evidence": "preserved"},
    )


def _market() -> MarketView:
    return MarketView(
        ticker=TICKER,
        title="MLB test",
        vertical=Vertical.SPORTS,
        status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        yes_bid=40,
        yes_ask=50,
        no_bid=50,
        no_ask=60,
        volume=100,
        liquidity=100,
        raw={"category": "Sports"},
    )


def _risk_state() -> RiskState:
    return RiskState(
        bankroll_cents=10_000,
        equity_peak_cents=10_000,
        stage=Stage.SHADOW_ONLY,
        open_exposure_cents=0,
        open_markets=0,
        daily_pnl_cents=0,
        settled_count_at_stage=0,
        realized_pnl_per_contract_cents=0.0,
    )


def test_c1_reprice_recomputes_metadata_without_increasing_risk_budget():
    decision = _decision()
    executor = Executor(
        SessionMode.SHADOW,
        quote_fn=lambda _ticker: {
            "yes_ask": 50,
            "yes_bid": 45,
            "yes_ask_levels": [[50, 10]],
            "book_received_at": datetime.now(timezone.utc).isoformat(),
        },
        execution_policy=ExecutionPolicy.taker_only(taker_min_ev_cents=3.0),
    )

    repriced = executor._apply_taker_policy(decision)

    assert isinstance(repriced, Decision)
    assert repriced.price_cents == 50
    assert repriced.count == 2
    assert repriced.notional_cents == 100 <= decision.notional_cents
    expected_fee = kalshi_taker_fee_cents(50, 2, TICKER)
    expected_ev = 70.0 - 50 - expected_fee / 2
    assert repriced.ev_cents_per_contract == pytest.approx(round(expected_ev, 2))
    assert repriced.kelly_fraction == pytest.approx(round(kelly_fraction_yes(0.70, 50), 4))
    assert repriced.risk_snapshot["risk_evidence"] == "preserved"

    outcome = asyncio.run(executor.execute(decision, market=_market()))
    assert outcome.kind is OutcomeKind.SHADOW
    assert outcome.fill_count == 0
    assert outcome.detail["liquidity_role"] == "taker"
    assert outcome.detail["submitted_price_cents"] == 50
    assert outcome.detail["submitted_count"] == 2
    assert outcome.detail["submitted_notional_cents"] == 100
    assert outcome.detail["submitted_ev_cents_per_contract"] == pytest.approx(
        round(expected_ev, 2)
    )


def test_open_positions_use_submitted_terms_then_witnessed_fill(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        decision = _decision()
        ledger.record_decision(decision)
        ledger.record_outcome(TradeOutcome(
            decision_id=decision.decision_id,
            market_ticker=TICKER,
            kind=OutcomeKind.SHADOW,
            order_id="shadow-d-taker",
            fill_count=0,
            fill_price_cents=50,
            pnl_cents=None,
            broker_contacted=False,
            detail={
                "submitted_price_cents": 50,
                "submitted_count": 2,
                "submitted_notional_cents": 100,
                "liquidity_role": "taker",
            },
        ))

        pending = ledger.open_decisions("shadow")[0]
        assert pending["decision_price_cents"] == 40
        assert pending["price_cents"] == 50
        assert pending["fill_price_cents"] is None
        assert pending["count"] == pending["reserved_count"] == 2

        ledger.record_outcome(TradeOutcome(
            decision_id=decision.decision_id,
            market_ticker=TICKER,
            kind=OutcomeKind.FILLED,
            order_id="shadow-d-taker",
            fill_count=2,
            fill_price_cents=48,
            pnl_cents=None,
            broker_contacted=False,
            detail={"liquidity_role": "taker", "fill_price_source": "witness"},
        ))
        filled = ledger.open_decisions("shadow")[0]
        assert filled["decision_price_cents"] == 40
        assert filled["submitted_price_cents"] == 50
        assert filled["price_cents"] == filled["fill_price_cents"] == 48
        assert filled["filled_count"] == filled["reserved_count"] == 2
        assert filled["liquidity_role"] == "taker"
    finally:
        ledger.close()


def test_live_reconciliation_records_weighted_price_role_cost_and_fee(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        decision = _decision()
        ledger.record_decision(decision)
        ledger.record_outcome(TradeOutcome(
            decision_id=decision.decision_id,
            market_ticker=TICKER,
            kind=OutcomeKind.ACCEPTED,
            order_id="order-1",
            fill_count=0,
            fill_price_cents=50,
            pnl_cents=None,
            broker_contacted=True,
            detail={
                "submitted_price_cents": 50,
                "submitted_count": 2,
                "submitted_notional_cents": 100,
                "liquidity_role": "taker",
            },
        ))
        reconciler = Reconciler(
            ledger,
            order_status_fn=lambda _order_id: {"order": {
                "status": "executed",
                "fill_count_fp": "2.00",
                "taker_fill_cost_dollars": "0.9000",
                "maker_fill_cost_dollars": "0.0000",
                "taker_fees_dollars": "0.0400",
                "maker_fees_dollars": "0.0000",
            }},
        )

        updates = reconciler.reconcile_open_orders()

        assert len(updates) == 1
        outcome = updates[0]
        assert outcome.kind is OutcomeKind.FILLED
        assert outcome.fill_count == 2
        assert outcome.fill_price_cents == 45
        assert outcome.detail["liquidity_role"] == "taker"
        assert outcome.detail["fill_price_source"] == "broker_fill_cost"
        assert outcome.detail["fill_cost_cents"] == 90
        assert outcome.detail["execution_fee_cents"] == 4

        position = ledger.open_decisions("live")[0]
        assert position["price_cents"] == position["fill_price_cents"] == 45
        assert position["fill_cost_cents"] == 90
        assert position["execution_fee_cents"] == 4
        assert position["liquidity_role"] == "taker"
    finally:
        ledger.close()


@pytest.mark.parametrize(
    "broker_fill_count",
    ["0.50", "-1.00", "NaN", "not-a-number"],
)
def test_nonintegral_or_invalid_terminal_fill_is_retained_without_truncation(
    tmp_path,
    broker_fill_count,
):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        decision = _decision()
        ledger.record_decision(decision)
        ledger.record_outcome(TradeOutcome(
            decision_id=decision.decision_id,
            market_ticker=TICKER,
            kind=OutcomeKind.ACCEPTED,
            order_id="order-fractional",
            fill_count=0,
            fill_price_cents=50,
            pnl_cents=None,
            broker_contacted=True,
            detail={
                "submitted_price_cents": 50,
                "submitted_count": 2,
                "submitted_notional_cents": 100,
                "liquidity_role": "maker",
            },
        ))
        reconciler = Reconciler(
            ledger,
            order_status_fn=lambda _order_id: {"order": {
                "status": "canceled",
                "fill_count_fp": broker_fill_count,
                "maker_fill_cost_dollars": "0.2500",
            }},
        )

        updates = reconciler.reconcile_open_orders()

        assert updates == []
        pending = ledger.open_decisions("live")[0]
        assert pending["order_active"] == 1
        assert pending["filled_count"] == 0
    finally:
        ledger.close()


@pytest.mark.parametrize("liquidity_role", ["maker", "taker"])
def test_settlement_uses_witnessed_price_and_correct_role_fee(liquidity_role):
    class _Ledger:
        def __init__(self):
            self.outcomes = []

        def record_outcome(self, outcome):
            self.outcomes.append(outcome)

    ledger = _Ledger()
    brain = object.__new__(PredatorBrain)
    brain.mode = SessionMode.SHADOW
    brain.ledger = ledger
    position = {
        "decision_id": f"d-{liquidity_role}",
        "market_ticker": TICKER,
        "side": "yes",
        "price_cents": 40,
        "fill_price_cents": 50,
        "count": 10,
        "filled_count": 10,
        "order_id": f"o-{liquidity_role}",
        "liquidity_role": liquidity_role,
    }

    brain._close_position(_risk_state(), position, result_yes=True)

    expected = settlement_pnl_cents(
        "yes", 50, 10, True, TICKER, liquidity_role
    )
    assert ledger.outcomes[-1].pnl_cents == expected
    assert ledger.outcomes[-1].fill_price_cents == 50
    assert ledger.outcomes[-1].detail["liquidity_role"] == liquidity_role
    expected_fee = (
        kalshi_maker_fee_cents(50, 10, TICKER)
        if liquidity_role == "maker"
        else kalshi_taker_fee_cents(50, 10, TICKER)
    )
    assert expected == 500 - expected_fee


def test_settlement_prefers_broker_witnessed_aggregate_cost_and_fee():
    assert settlement_pnl_cents(
        "yes",
        45,
        2,
        True,
        TICKER,
        "taker",
        fee_cents=4,
        fill_cost_cents=90,
    ) == 106
