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
    kalshi_maker_fee_cents,
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
CRYPTO_MIN_EV_CENTS = 8.0
CRYPTO_MAX_PRICE_CENTS = 75
# Size and trade from a conservative probability inside the fused uncertainty
# band.  This prevents a noisy point estimate from spending its entire claimed
# edge while still allowing strong, well-supported disagreements to trade.
CONFIDENCE_HAIRCUT_SIGMAS = 0.5
# Extremely wide or one-sided books create phantom midpoints and only fill
# after adverse moves. Historical shadow orders at 60-96c spreads consumed
# scarce slots without filling. Require an executable two-sided market.
MAX_ACTIONABLE_SPREAD_CENTS = 20


def _abstain(
    market: MarketView,
    forecast: Forecast,
    reason: str,
    risk_snapshot: dict,
    *,
    side: str = "yes",
    price_cents: int = 0,
    ev_cents: float = 0.0,
    kelly: float = 0.0,
) -> Decision:
    """Record the best rejected candidate so policy tuning has evidence."""
    return Decision(
        decision_id=uuid.uuid4().hex[:16],
        market_ticker=market.ticker,
        action=DecisionAction.ABSTAIN,
        side=side,
        price_cents=price_cents,
        count=0,
        ev_cents_per_contract=round(ev_cents, 2),
        kelly_fraction=round(kelly, 4),
        notional_cents=0,
        forecast=forecast,
        risk_snapshot=risk_snapshot,
        abstain_reason=reason,
    )


class Allocator:
    def __init__(
        self,
        risk_brain: RiskBrain,
        min_ev_cents: float = MIN_EV_CENTS,
        performance_guard=None,
        execution_policy=None,
    ):
        self.risk_brain = risk_brain
        self.min_ev_cents = min_ev_cents
        self.performance_guard = performance_guard
        self.execution_policy = execution_policy

    @property
    def _immediate_taker(self) -> bool:
        return getattr(self.execution_policy, "mode", None) == "taker"

    def _entry_price(
        self, best_bid: int | None, best_ask: int | None, fair_cents: float,
    ) -> int | None:
        if self._immediate_taker:
            return int(best_ask) if best_ask is not None and 1 <= int(best_ask) <= 99 else None
        return self._maker_price(best_bid, best_ask, fair_cents)

    def _entry_fee(self, price: int, ticker: str) -> int:
        if self._immediate_taker:
            return kalshi_taker_fee_cents(price, 1, ticker)
        return kalshi_maker_fee_cents(price, 1, ticker)

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
        if self.performance_guard is not None:
            reason = self.performance_guard.reason_for(market, forecast)
            if reason:
                return _abstain(market, forecast, reason, snapshot)
        if forecast.uncertainty > MAX_UNCERTAINTY:
            return _abstain(market, forecast, f"uncertainty {forecast.uncertainty:.2f} too high", snapshot)
        quotes = (market.yes_bid, market.yes_ask, market.no_bid, market.no_ask)
        if any(quote is None for quote in quotes):
            return _abstain(market, forecast, "two-sided executable book required", snapshot)
        yes_spread = int(market.yes_ask) - int(market.yes_bid)
        no_spread = int(market.no_ask) - int(market.no_bid)
        if yes_spread <= 0 or no_spread <= 0:
            return _abstain(market, forecast, "crossed or invalid binary book", snapshot)
        if max(yes_spread, no_spread) > MAX_ACTIONABLE_SPREAD_CENTS:
            return _abstain(
                market, forecast,
                f"spread {max(yes_spread, no_spread)}c exceeds actionable maximum "
                f"{MAX_ACTIONABLE_SPREAD_CENTS}c",
                snapshot,
            )

        # Stage horizon: early stages hold few slots, and a slot parked in a
        # market that settles weeks out freezes evidence accrual. Far-dated
        # markets wait for CRUISE.
        max_days = float(STAGE_LIMITS[state.stage].get("max_days_to_close") or 0)
        if max_days > 0:
            try:
                close = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
                days_out = (close - datetime.now(timezone.utc)).total_seconds() / 86400.0
            except Exception:
                return _abstain(
                    market, forecast, "missing or invalid close time at bounded-risk stage", snapshot
                )
            if days_out < 0:
                return _abstain(market, forecast, "market close time already passed", snapshot)
            if days_out > max_days:
                return _abstain(market, forecast,
                                f"close {days_out:.1f}d out exceeds stage horizon {max_days:.0f}d", snapshot)

        # Evaluate YES and NO sides symmetrically: buying NO at price p_no is
        # a YES-frame bet at probability (1 - q).
        candidates = []
        q = forecast.probability_yes
        yes_price = self._entry_price(market.yes_bid, market.yes_ask, q * 100.0)
        max_price = CRYPTO_MAX_PRICE_CENTS if market.vertical.value == "CRYPTO" else MAX_PRICE_CENTS
        if yes_price is not None and yes_price <= max_price:
            conservative_q = max(0.005, q - CONFIDENCE_HAIRCUT_SIGMAS * forecast.uncertainty)
            ev = (conservative_q * 100.0 - yes_price
                  - self._entry_fee(yes_price, market.ticker))
            candidates.append(("yes", yes_price, conservative_q, ev))
        no_fair = (1.0 - q) * 100.0
        no_price = self._entry_price(market.no_bid, market.no_ask, no_fair)
        if no_price is not None and no_price <= max_price:
            conservative_no = max(
                0.005, (1.0 - q) - CONFIDENCE_HAIRCUT_SIGMAS * forecast.uncertainty
            )
            ev = (conservative_no * 100.0 - no_price
                  - self._entry_fee(no_price, market.ticker))
            candidates.append(("no", no_price, conservative_no, ev))

        if not candidates:
            entry_style = "taker" if self._immediate_taker else "maker"
            return _abstain(market, forecast, f"no viable {entry_style} price", snapshot)
        side, price, win_prob, ev = max(candidates, key=lambda c: c[3])
        kelly = kelly_fraction_yes(win_prob, price)
        min_ev = max(self.min_ev_cents, CRYPTO_MIN_EV_CENTS) \
            if market.vertical.value == "CRYPTO" else self.min_ev_cents
        if self._immediate_taker:
            min_ev = max(
                min_ev,
                float(getattr(self.execution_policy, "taker_min_ev_cents", 0.0) or 0.0),
            )
            edge_floor = float(
                getattr(self.execution_policy, "taker_min_edge_cents", 0.0) or 0.0
            )
            gross_edge = win_prob * 100.0 - price
            if gross_edge < edge_floor:
                return _abstain(
                    market, forecast,
                    f"gross edge {gross_edge:.1f}c below taker threshold {edge_floor:.1f}c",
                    snapshot, side=side, price_cents=price, ev_cents=ev, kelly=kelly,
                )
        if ev < min_ev:
            return _abstain(
                market, forecast, f"ev {ev:.1f}c below threshold {min_ev:.1f}c", snapshot,
                side=side, price_cents=price, ev_cents=ev, kelly=kelly,
            )

        budget: OrderBudget = self.risk_brain.order_budget(
            state, market.ticker, market_exposure_cents, kelly,
            group_exposure_cents=group_exposure_cents, group_open_count=group_open_count,
        )
        if not budget.allowed:
            return _abstain(
                market, forecast, f"risk brain: {budget.reason}", budget.risk_snapshot,
                side=side, price_cents=price, ev_cents=ev, kelly=kelly,
            )
        if budget.max_notional_cents < price:
            return _abstain(
                market, forecast,
                f"risk brain: remaining budget {budget.max_notional_cents}c below one "
                f"contract at {price}c",
                budget.risk_snapshot, side=side, price_cents=price,
                ev_cents=ev, kelly=kelly,
            )
        count = budget.max_notional_cents // price
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
