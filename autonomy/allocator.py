"""Allocator: forecast -> sized, priced, fee-aware decision.

Maker-first: quotes rest inside the spread at an edge-preserving price
instead of crossing, because on Kalshi the taker pays the fee — patience is
alpha. Every decision, including abstentions, is recorded so the learner can
audit selectivity as well as accuracy.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from autonomy.ontology import Decision, DecisionAction, Forecast, MarketView
from autonomy.risk_brain import (
    STAGE_LIMITS,
    OrderBudget,
    RiskBrain,
    RiskState,
    kalshi_taker_fee_cents,
    kelly_fraction_yes,
)

# Minimum fee-adjusted expected value per contract (cents) before we act.
MIN_EV_CENTS = 3.0
# Minimum fused-forecast confidence: sigma above this means we don't know
# enough to disagree with anyone.
MAX_UNCERTAINTY = 0.35
# Never buy above this price: deep-favorite YES has poor payoff asymmetry
# for a maker-first strategy and is where settlement-rule surprises live.
MAX_PRICE_CENTS = 90


def _abstain(market: MarketView, forecast: Forecast, reason: str, risk_snapshot: dict) -> Decision:
    return Decision(
        decision_id=uuid.uuid4().hex[:16],
        market_ticker=market.ticker,
        action=DecisionAction.ABSTAIN,
        side="yes",
        price_cents=0,
        count=0,
        ev_cents_per_contract=0.0,
        kelly_fraction=0.0,
        notional_cents=0,
        forecast=forecast,
        risk_snapshot=risk_snapshot,
        abstain_reason=reason,
    )


class Allocator:
    def __init__(self, risk_brain: RiskBrain, min_ev_cents: float = MIN_EV_CENTS):
        self.risk_brain = risk_brain
        self.min_ev_cents = min_ev_cents

    def _maker_price(self, best_bid: int | None, best_ask: int | None, fair_cents: float) -> int | None:
        """Rest one tick inside the current bid, never above our fair value."""
        if best_bid is not None and best_ask is not None and best_ask - best_bid > 1:
            candidate = best_bid + 1
        elif best_bid is not None:
            candidate = best_bid
        elif best_ask is not None:
            candidate = max(1, best_ask - 1)
        else:
            candidate = int(fair_cents)  # empty book: quote at fair
        price = min(candidate, int(fair_cents) - 1)
        return price if 1 <= price <= 99 else None

    def decide(self, market: MarketView, forecast: Forecast, state: RiskState,
               market_exposure_cents: int = 0, group_exposure_cents: int = 0,
               group_open_count: int = 0) -> Decision:
        snapshot: dict = {}
        if forecast.uncertainty > MAX_UNCERTAINTY:
            return _abstain(market, forecast, f"uncertainty {forecast.uncertainty:.2f} too high", snapshot)

        # Stage horizon: early stages hold few slots, and a slot parked in a
        # market that settles weeks out freezes evidence accrual. Far-dated
        # markets wait for CRUISE.
        max_days = float(STAGE_LIMITS[state.stage].get("max_days_to_close") or 0)
        if max_days > 0:
            try:
                close = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
                days_out = (close - datetime.now(timezone.utc)).total_seconds() / 86400.0
            except Exception:
                days_out = None
            if days_out is not None and days_out > max_days:
                return _abstain(market, forecast,
                                f"close {days_out:.1f}d out exceeds stage horizon {max_days:.0f}d", snapshot)

        # Evaluate YES and NO sides symmetrically: buying NO at price p_no is
        # a YES-frame bet at probability (1 - q).
        candidates = []
        q = forecast.probability_yes
        yes_price = self._maker_price(market.yes_bid, market.yes_ask, q * 100.0)
        if yes_price is not None and yes_price <= MAX_PRICE_CENTS:
            ev = q * 100.0 - yes_price - kalshi_taker_fee_cents(yes_price, 1)
            candidates.append(("yes", yes_price, q, ev))
        no_fair = (1.0 - q) * 100.0
        no_price = self._maker_price(market.no_bid, market.no_ask, no_fair)
        if no_price is not None and no_price <= MAX_PRICE_CENTS:
            ev = (1.0 - q) * 100.0 - no_price - kalshi_taker_fee_cents(no_price, 1)
            candidates.append(("no", no_price, 1.0 - q, ev))

        if not candidates:
            return _abstain(market, forecast, "no viable maker price", snapshot)
        side, price, win_prob, ev = max(candidates, key=lambda c: c[3])
        if ev < self.min_ev_cents:
            return _abstain(market, forecast, f"ev {ev:.1f}c below threshold", snapshot)

        kelly = kelly_fraction_yes(win_prob, price)
        budget: OrderBudget = self.risk_brain.order_budget(
            state, market.ticker, market_exposure_cents, kelly,
            group_exposure_cents=group_exposure_cents, group_open_count=group_open_count,
        )
        if not budget.allowed:
            return _abstain(market, forecast, f"risk brain: {budget.reason}", budget.risk_snapshot)
        count = max(1, budget.max_notional_cents // price)
        notional = count * price
        return Decision(
            decision_id=uuid.uuid4().hex[:16],
            market_ticker=market.ticker,
            action=DecisionAction.BUY_YES if side == "yes" else DecisionAction.BUY_NO,
            side=side,
            price_cents=price,
            count=count,
            ev_cents_per_contract=round(ev, 2),
            kelly_fraction=round(kelly, 4),
            notional_cents=notional,
            forecast=forecast,
            risk_snapshot=budget.risk_snapshot,
        )
