"""Shadow fills credit only witnessed size: maker queue math + taker witness depth."""
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


TICKER = "KXBTC15M-26JUL221500-15"


def _decision(created_at: str, *, count: int = 4) -> Decision:
    forecast = Forecast(
        market_ticker=TICKER,
        probability_yes=0.80,
        uncertainty=0.10,
        sources_used={"model": 1.0},
        market_implied_yes=0.50,
        edge_yes=0.30,
        rationale="partial fill truth",
    )
    return Decision(
        decision_id="partial-truth",
        market_ticker=TICKER,
        action=DecisionAction.BUY_YES,
        side="yes",
        price_cents=52,
        count=count,
        ev_cents_per_contract=25.0,
        kelly_fraction=0.10,
        notional_cents=52 * count,
        forecast=forecast,
        risk_snapshot={},
        created_at=created_at,
    )


def _market(ask: int, *, ask_size_fp: float | None = None) -> MarketView:
    raw = {}
    if ask_size_fp is not None:
        raw["yes_ask_size_fp"] = ask_size_fp
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
        raw=raw,
    )


def _submission(
    created_at: str, *, role: str, count: int = 4, queue_ahead: float | None = None,
) -> TradeOutcome:
    detail = {
        "state": "resting",
        "liquidity_role": role,
        "submitted_price_cents": 52,
        "submitted_count": count,
        "submitted_notional_cents": 52 * count,
    }
    if role == "taker":
        detail["executable_liquidity"] = {
            "liquidity_evidence_version": LIQUIDITY_EVIDENCE_VERSION,
            "quote_received_at": created_at,
            "executable_count": count,
            "submitted_limit_price_cents": 52,
            "fill_status": "unfilled_plan_only",
        }
    if queue_ahead is not None:
        detail["queue_snapshot_available"] = True
        detail["queue_ahead_contracts"] = queue_ahead
    return TradeOutcome(
        decision_id="partial-truth",
        market_ticker=TICKER,
        kind=OutcomeKind.SHADOW,
        order_id="shadow-partial-truth",
        fill_count=0,
        fill_price_cents=52,
        pnl_cents=None,
        broker_contacted=False,
        detail=detail,
    )


def _trade(price_cents: int, count: float, at: datetime, trade_id: str) -> dict:
    return {
        "trade_id": trade_id,
        "taker_book_side": "ask",
        "yes_price_dollars": price_cents / 100.0,
        "count_fp": count,
        "created_time": at.isoformat(),
        "is_block_trade": False,
    }


def test_maker_partial_queue_clearance_credits_witnessed_remainder(tmp_path):
    now = datetime.now(timezone.utc)
    created = now - timedelta(seconds=30)
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(_decision(created.isoformat()))
        ledger.record_outcome(
            _submission(created.isoformat(), role="maker", queue_ahead=5.0)
        )

        # 7 contracts trade at the limit: queue of 5 clears, then 2 of our 4.
        trades = [_trade(52, 7.0, created + timedelta(seconds=5), "t1")]
        rec = Reconciler(ledger, fetch_shadow_trades=lambda *_a: trades)
        updates = rec.reconcile_shadow_orders([_market(60)], now=now)

        assert [u.kind for u in updates] == [OutcomeKind.FILLED]
        assert updates[0].fill_count == 2
        detail = updates[0].detail
        assert detail["reason"] == "shadow_maker_public_trade_queue_partially_consumed"
        assert detail["partial_fill_truth"] is True
        assert detail["remainder_canceled_conservative"] == 2
    finally:
        ledger.close()


def test_maker_queue_not_cleared_stays_unfilled(tmp_path):
    now = datetime.now(timezone.utc)
    created = now - timedelta(seconds=30)
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(_decision(created.isoformat()))
        ledger.record_outcome(
            _submission(created.isoformat(), role="maker", queue_ahead=5.0)
        )
        trades = [_trade(52, 4.0, created + timedelta(seconds=5), "t1")]
        rec = Reconciler(ledger, fetch_shadow_trades=lambda *_a: trades)
        assert rec.reconcile_shadow_orders([_market(60)], now=now) == []
    finally:
        ledger.close()


def test_taker_witness_depth_caps_fill_count(tmp_path):
    now = datetime.now(timezone.utc)
    created = now - timedelta(seconds=10)
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(_decision(created.isoformat()))
        ledger.record_outcome(_submission(created.isoformat(), role="taker"))

        # Displayed ask size 4 -> 50% haircut -> at most 2 of 4 fill.
        updates = Reconciler(ledger).reconcile_shadow_orders(
            [_market(51, ask_size_fp=4.0)], now=now,
        )
        assert [u.kind for u in updates] == [OutcomeKind.FILLED]
        assert updates[0].fill_count == 2
        detail = updates[0].detail
        assert detail["witness_ask_size_fp"] == 4.0
        assert detail["partial_fill_truth"] is True
        assert detail["remainder_canceled_conservative"] == 2
    finally:
        ledger.close()


def test_taker_witness_depth_too_small_defers_fill(tmp_path):
    now = datetime.now(timezone.utc)
    created = now - timedelta(seconds=10)
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(_decision(created.isoformat()))
        ledger.record_outcome(_submission(created.isoformat(), role="taker"))

        # Displayed size 1 -> haircut 0.5 -> cannot honestly fill even one.
        assert Reconciler(ledger).reconcile_shadow_orders(
            [_market(51, ask_size_fp=1.0)], now=now,
        ) == []
    finally:
        ledger.close()


def test_taker_without_witness_sizes_keeps_submit_cap_but_discloses(tmp_path):
    now = datetime.now(timezone.utc)
    created = now - timedelta(seconds=10)
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_decision(_decision(created.isoformat()))
        ledger.record_outcome(_submission(created.isoformat(), role="taker"))

        updates = Reconciler(ledger).reconcile_shadow_orders(
            [_market(51)], now=now,
        )
        assert [u.kind for u in updates] == [OutcomeKind.FILLED]
        assert updates[0].fill_count == 4
        assert updates[0].detail["witness_depth_unverified"] is True
    finally:
        ledger.close()
