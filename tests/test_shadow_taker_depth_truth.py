"""Shadow taker fills require persisted executable-depth evidence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.executable_liquidity import LIQUIDITY_EVIDENCE_VERSION
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import (
    Decision,
    DecisionAction,
    Forecast,
    MarketView,
    OutcomeKind,
    TradeOutcome,
    Vertical,
)
from autonomy.reconciler import Reconciler


TICKER = "KXBTC15M-26JUL211500-15"


def _decision(created_at: str) -> Decision:
    forecast = Forecast(
        market_ticker=TICKER,
        probability_yes=0.80,
        uncertainty=0.10,
        sources_used={"model": 1.0},
        market_implied_yes=0.50,
        edge_yes=0.30,
        rationale="shadow taker depth truth",
    )
    return Decision(
        decision_id="shadow-depth",
        market_ticker=TICKER,
        action=DecisionAction.BUY_YES,
        side="yes",
        price_cents=52,
        count=2,
        ev_cents_per_contract=25.0,
        kelly_fraction=0.10,
        notional_cents=104,
        forecast=forecast,
        risk_snapshot={},
        created_at=created_at,
    )


def _market(ask: int) -> MarketView:
    return MarketView(
        ticker=TICKER,
        title="",
        vertical=Vertical.CRYPTO,
        status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        yes_bid=ask - 2,
        yes_ask=ask,
        no_bid=100 - ask,
        no_ask=102 - ask,
        volume=100,
        liquidity=1_000,
    )


def _submission(created_at: str, *, include_depth: bool) -> TradeOutcome:
    detail = {
        "state": "resting",
        "liquidity_role": "taker",
        "submitted_price_cents": 52,
        "submitted_count": 2,
        "submitted_notional_cents": 104,
    }
    if include_depth:
        detail["executable_liquidity"] = {
            "liquidity_evidence_version": LIQUIDITY_EVIDENCE_VERSION,
            "quote_received_at": created_at,
            "executable_count": 2,
            "submitted_limit_price_cents": 52,
            "fill_status": "unfilled_plan_only",
        }
    return TradeOutcome(
        decision_id="shadow-depth",
        market_ticker=TICKER,
        kind=OutcomeKind.SHADOW,
        order_id="shadow-shadow-depth",
        fill_count=0,
        fill_price_cents=52,
        pnl_cents=None,
        broker_contacted=False,
        detail=detail,
    )


def test_shadow_taker_never_fills_from_top_ask_without_depth_evidence(tmp_path):
    now = datetime.now(timezone.utc)
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(_decision((now - timedelta(seconds=10)).isoformat()))
        ledger.record_outcome(_submission(now.isoformat(), include_depth=False))

        assert Reconciler(ledger).reconcile_shadow_orders([_market(50)], now=now) == []
        pending = ledger.open_decisions("shadow")[0]
        assert pending["filled_count"] == 0 and pending["order_active"] == 1
    finally:
        ledger.close()


def test_shadow_taker_missing_depth_expires_without_fabricated_fill(tmp_path):
    now = datetime.now(timezone.utc)
    created = now - timedelta(seconds=61)
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(_decision(created.isoformat()))
        ledger.record_outcome(_submission(created.isoformat(), include_depth=False))

        updates = Reconciler(ledger).reconcile_shadow_orders([_market(50)], now=now)
        assert [row.kind for row in updates] == [OutcomeKind.EXPIRED]
        assert updates[0].fill_count == 0
        assert updates[0].detail["reason"] == (
            "shadow_taker_missing_executable_depth_evidence"
        )
    finally:
        ledger.close()


def test_shadow_taker_depth_cap_plus_later_ask_can_simulate_only_submitted_count(tmp_path):
    now = datetime.now(timezone.utc)
    created = now - timedelta(seconds=10)
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(_decision(created.isoformat()))
        ledger.record_outcome(_submission(created.isoformat(), include_depth=True))

        updates = Reconciler(ledger).reconcile_shadow_orders([_market(51)], now=now)
        assert [row.kind for row in updates] == [OutcomeKind.FILLED]
        assert updates[0].fill_count == 2
        assert updates[0].fill_price_cents == 52
        assert updates[0].detail["simulated_fill_authority"] == (
            "depth_haircut_plus_later_ask"
        )
        assert updates[0].detail["executable_liquidity"]["executable_count"] == 2
    finally:
        ledger.close()
