"""Fail-closed executable-liquidity planning for taker orders.

Top-of-book price is not executable evidence for an arbitrary quantity.  This
module converts a freshly witnessed side-specific ask ladder into a bounded
plan that:

* rejects missing, stale, crossed, or excessively wide books;
* discounts displayed depth before sizing, reducing partial-fill/race risk;
* caps the submitted quantity by the original risk-brain notional;
* limits both level and VWAP slippage; and
* recomputes expected value after the modeled fill cost and taker fees.

The plan is evidence, not a fill claim.  Actual fill price, quantity, role, and
fees still come only from the simulator/broker reconciliation witness.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from autonomy.fees import kalshi_taker_fee_cents

LIQUIDITY_EVIDENCE_VERSION = "executable_depth_v1"
MAX_FRESH_QUOTE_AGE_SECONDS = 5.0
MAX_FUTURE_QUOTE_SKEW_SECONDS = 1.0
MAX_EXECUTABLE_SPREAD_CENTS = 20
MAX_TAKER_LEVEL_SLIPPAGE_CENTS = 3
MAX_TAKER_VWAP_SLIPPAGE_CENTS = 2.0
DISPLAYED_DEPTH_SAFETY_FRACTION = 0.50


@dataclass(frozen=True)
class QuoteFreshness:
    valid: bool
    reason: str
    age_seconds: float | None
    received_at: str | None


@dataclass(frozen=True)
class ExecutableLiquidityPlan:
    requested_count: int
    executable_count: int
    top_ask_cents: int
    limit_price_cents: int
    modeled_vwap_cents: float
    visible_cost_cents: int
    worst_case_notional_cents: int
    modeled_fee_cents: int
    net_ev_cents_per_contract: float
    gross_edge_cents: float
    spread_cents: int
    level_slippage_cents: int
    vwap_slippage_cents: float
    visible_depth_contracts: int
    usable_depth_contracts: int
    depth_safety_fraction: float
    level_fills: tuple[tuple[int, int], ...]

    def evidence(self, quote_received_at: str | None) -> dict[str, Any]:
        return {
            "liquidity_evidence_version": LIQUIDITY_EVIDENCE_VERSION,
            "quote_received_at": quote_received_at,
            "requested_count": self.requested_count,
            "executable_count": self.executable_count,
            "top_ask_cents": self.top_ask_cents,
            "submitted_limit_price_cents": self.limit_price_cents,
            "modeled_vwap_cents": round(self.modeled_vwap_cents, 4),
            "visible_cost_cents": self.visible_cost_cents,
            "worst_case_notional_cents": self.worst_case_notional_cents,
            "modeled_fee_cents": self.modeled_fee_cents,
            "net_ev_cents_per_contract": round(self.net_ev_cents_per_contract, 4),
            "gross_edge_cents": round(self.gross_edge_cents, 4),
            "spread_cents": self.spread_cents,
            "level_slippage_cents": self.level_slippage_cents,
            "vwap_slippage_cents": round(self.vwap_slippage_cents, 4),
            "visible_depth_contracts": self.visible_depth_contracts,
            "usable_depth_contracts": self.usable_depth_contracts,
            "depth_safety_fraction": self.depth_safety_fraction,
            "level_fills": [list(level) for level in self.level_fills],
            "depth_capped": self.executable_count < self.requested_count,
            "fill_status": "unfilled_plan_only",
        }


@dataclass(frozen=True)
class LiquidityAssessment:
    allowed: bool
    reason: str
    plan: ExecutableLiquidityPlan | None
    detail: dict[str, Any]


def _reject(reason: str, **detail: Any) -> LiquidityAssessment:
    return LiquidityAssessment(False, reason, None, detail)


def _parse_received_at(value: Any) -> tuple[float | None, str | None]:
    if isinstance(value, datetime):
        stamp = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return stamp.timestamp(), stamp.astimezone(timezone.utc).isoformat()
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        stamp = datetime.fromtimestamp(float(value), timezone.utc)
        return stamp.timestamp(), stamp.isoformat()
    if isinstance(value, str):
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None, None
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.timestamp(), stamp.astimezone(timezone.utc).isoformat()
    return None, None


def evaluate_quote_freshness(
    quote: dict[str, Any] | None,
    *,
    now_ts: float,
    max_age_seconds: float = MAX_FRESH_QUOTE_AGE_SECONDS,
    max_future_skew_seconds: float = MAX_FUTURE_QUOTE_SKEW_SECONDS,
) -> QuoteFreshness:
    """Validate the local receipt witness attached to a direct book read."""
    if not isinstance(quote, dict):
        return QuoteFreshness(False, "taker_no_fresh_book", None, None)
    observed_ts, received_at = _parse_received_at(quote.get("book_received_at"))
    if observed_ts is None:
        return QuoteFreshness(False, "taker_quote_timestamp_missing", None, None)
    age = float(now_ts) - observed_ts
    if age < -float(max_future_skew_seconds):
        return QuoteFreshness(False, "taker_quote_timestamp_future", age, received_at)
    if age > float(max_age_seconds):
        return QuoteFreshness(False, "taker_quote_stale", age, received_at)
    return QuoteFreshness(True, "fresh", max(0.0, age), received_at)


def _whole_contract_levels(quote: dict[str, Any], side: str) -> list[tuple[int, int]]:
    key = f"{side}_ask_levels"
    raw = quote.get(key)
    if raw is None:
        ask = quote.get(f"{side}_ask")
        size = quote.get(f"{side}_ask_size")
        raw = [[ask, size]] if ask is not None and size is not None else []
    if not isinstance(raw, (list, tuple)):
        return []
    merged: dict[int, int] = {}
    for item in raw:
        if isinstance(item, dict):
            raw_price = item.get("price_cents", item.get("price"))
            raw_count = item.get("count", item.get("size"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            raw_price, raw_count = item[0], item[1]
        else:
            continue
        try:
            price_float = float(raw_price)
            count_float = float(raw_count)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(price_float) or not math.isfinite(count_float):
            continue
        price = int(price_float)
        count = math.floor(count_float)
        if price_float != price or not (1 <= price <= 99) or count < 1:
            continue
        merged[price] = merged.get(price, 0) + count
    return sorted(merged.items())


def assess_taker_liquidity(
    quote: dict[str, Any],
    *,
    side: str,
    requested_count: int,
    notional_cap_cents: int,
    probability_side: float,
    market_ticker: str,
    min_ev_cents: float,
    min_edge_cents: float,
    max_spread_cents: int = MAX_EXECUTABLE_SPREAD_CENTS,
    max_level_slippage_cents: int = MAX_TAKER_LEVEL_SLIPPAGE_CENTS,
    max_vwap_slippage_cents: float = MAX_TAKER_VWAP_SLIPPAGE_CENTS,
    depth_safety_fraction: float = DISPLAYED_DEPTH_SAFETY_FRACTION,
) -> LiquidityAssessment:
    """Build a conservative, quantity-aware taker plan from a fresh book."""
    if side not in {"yes", "no"}:
        return _reject("taker_side_invalid", side=side)
    if requested_count < 1 or notional_cap_cents < 1:
        return _reject("taker_reprice_exceeds_notional_cap")
    if not (0.0 <= probability_side <= 1.0):
        return _reject("taker_probability_invalid")
    if not (0.0 < depth_safety_fraction <= 1.0):
        return _reject("taker_depth_safety_invalid")

    levels = _whole_contract_levels(quote, side)
    if not levels:
        return _reject("taker_executable_depth_missing")
    top_ask = levels[0][0]
    try:
        quoted_ask = int(quote.get(f"{side}_ask"))
        bid = int(quote.get(f"{side}_bid"))
    except (TypeError, ValueError):
        return _reject("taker_two_sided_book_required")
    if quoted_ask != top_ask:
        return _reject(
            "taker_book_inconsistent",
            quoted_ask_cents=quoted_ask,
            ladder_top_ask_cents=top_ask,
        )
    spread = top_ask - bid
    if spread <= 0:
        return _reject("taker_book_crossed", bid_cents=bid, ask_cents=top_ask)
    if spread > max_spread_cents:
        return _reject(
            "taker_spread_exceeds_cap",
            spread_cents=spread,
            maximum_spread_cents=max_spread_cents,
        )

    visible_depth = sum(
        count for price, count in levels
        if price - top_ask <= max_level_slippage_cents
    )
    level_fills: list[tuple[int, int]] = []
    selected = 0
    capacity_seen = 0
    rejection_at_top: str | None = None
    for price, visible_count in levels:
        if price - top_ask > max_level_slippage_cents:
            break
        gross_edge = probability_side * 100.0 - price
        single_fee = kalshi_taker_fee_cents(price, 1, market_ticker)
        if gross_edge < min_edge_cents:
            rejection_at_top = rejection_at_top or "taker_edge_below_min"
            break
        if gross_edge - single_fee < min_ev_cents:
            rejection_at_top = rejection_at_top or "taker_ev_below_min"
            break
        usable_count = math.floor(visible_count * depth_safety_fraction)
        capacity_seen += usable_count
        if usable_count < 1:
            continue
        remaining_requested = requested_count - selected
        maximum_total_at_limit = notional_cap_cents // price
        remaining_budget_count = maximum_total_at_limit - selected
        take = min(usable_count, remaining_requested, remaining_budget_count)
        if take > 0:
            level_fills.append((price, take))
            selected += take
        if selected >= requested_count:
            break

    if selected < 1:
        if rejection_at_top is not None:
            return _reject(rejection_at_top, top_ask_cents=top_ask)
        if notional_cap_cents < top_ask:
            return _reject(
                "taker_reprice_exceeds_notional_cap",
                top_ask_cents=top_ask,
                notional_cap_cents=notional_cap_cents,
            )
        return _reject(
            "taker_depth_below_safety_floor",
            visible_depth_contracts=visible_depth,
            depth_safety_fraction=depth_safety_fraction,
        )

    visible_cost = sum(price * count for price, count in level_fills)
    modeled_fee = sum(
        kalshi_taker_fee_cents(price, count, market_ticker)
        for price, count in level_fills
    )
    limit_price = level_fills[-1][0]
    worst_case_notional = limit_price * selected
    modeled_vwap = visible_cost / selected
    vwap_slippage = modeled_vwap - top_ask
    if vwap_slippage > max_vwap_slippage_cents:
        return _reject(
            "taker_vwap_slippage_exceeds_cap",
            vwap_slippage_cents=round(vwap_slippage, 4),
            maximum_vwap_slippage_cents=max_vwap_slippage_cents,
        )
    net_ev = probability_side * 100.0 - (visible_cost + modeled_fee) / selected
    gross_edge = probability_side * 100.0 - modeled_vwap
    if net_ev < min_ev_cents:
        return _reject("taker_ev_below_min", net_ev_cents_per_contract=net_ev)
    if gross_edge < min_edge_cents:
        return _reject("taker_edge_below_min", gross_edge_cents=gross_edge)
    if worst_case_notional > notional_cap_cents:
        return _reject("taker_reprice_exceeds_notional_cap")

    plan = ExecutableLiquidityPlan(
        requested_count=requested_count,
        executable_count=selected,
        top_ask_cents=top_ask,
        limit_price_cents=limit_price,
        modeled_vwap_cents=modeled_vwap,
        visible_cost_cents=visible_cost,
        worst_case_notional_cents=worst_case_notional,
        modeled_fee_cents=modeled_fee,
        net_ev_cents_per_contract=net_ev,
        gross_edge_cents=gross_edge,
        spread_cents=spread,
        level_slippage_cents=limit_price - top_ask,
        vwap_slippage_cents=vwap_slippage,
        visible_depth_contracts=visible_depth,
        usable_depth_contracts=capacity_seen,
        depth_safety_fraction=depth_safety_fraction,
        level_fills=tuple(level_fills),
    )
    return LiquidityAssessment(True, "executable_depth_verified", plan, {})
