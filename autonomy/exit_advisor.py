"""Evidence-first exit planning for filled positions.

This module deliberately does not submit or cancel orders. It marks a possible
exit at the displayed bid, includes the taker fee, and requires that quoted
cash-out value beat an uncertainty-adjusted upper estimate of hold value. A
top-of-book quote is not called a fill: freshness and displayed depth are
recorded separately so the research evaluator can stress slippage honestly.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from autonomy.fees import kalshi_taker_fee_cents
from autonomy.ontology import Forecast, MarketView, Signal


EXIT_ARTIFACT_PATH = Path("runtime/autonomy/exit_advisories.json")
MIN_EXIT_ADVANTAGE_CENTS = 3.0
EXIT_CONFIDENCE_SIGMAS = 0.5
MAX_EXIT_QUOTE_AGE_SECONDS = 120.0


@dataclass(frozen=True)
class ExitAdvisory:
    decision_id: str
    market_ticker: str
    side: str
    probability_yes: float
    forecast_uncertainty: float
    action: str
    filled_count: int
    entry_price_cents: int
    executable_exit_cents: int | None
    advisory_created_at: str
    exit_quote_observed_at: str | None
    exit_quote_age_seconds: float | None
    exit_quote_fresh: bool
    exit_depth_contracts: int | None
    exit_depth_verified: bool
    entry_order_active: bool
    entry_liquidity_role: str
    entry_fee_cents: int | None
    entry_cost_cents: int | None
    entry_cost_source: str
    mark_change_cents: int | None
    time_to_close_hours: float | None
    fee_cents_per_contract: float | None
    hold_value_upper_cents: float | None
    exit_advantage_cents: float | None
    reason: str

    def to_signal(self) -> Signal:
        """Durable observational row for eventual settlement/exit replay."""
        return Signal(
            source="exit_advisor_shadow",
            market_ticker=self.market_ticker,
            probability_yes=self.probability_yes,
            uncertainty=self.forecast_uncertainty,
            rationale=f"{self.action}: {self.reason}",
            features={
                "evidence_version": "exit_advisor_v2",
                "observational_only": True,
                "policy_evidence_only": True,
                "probability_authority": False,
                "challenger_only": True,
                "promotion_eligible": False,
                "live_execution_enabled": False,
                "decision_id": self.decision_id,
                "position_side": self.side,
                "action": self.action,
                "filled_count": self.filled_count,
                "entry_price_cents": self.entry_price_cents,
                # Backward-compatible name. It is only a displayed bid; depth
                # and freshness below determine how strong the evidence is.
                "executable_exit_cents": self.executable_exit_cents,
                "quoted_exit_bid_cents": self.executable_exit_cents,
                "exit_quote_observed_at": self.exit_quote_observed_at,
                "exit_quote_age_seconds": self.exit_quote_age_seconds,
                "exit_quote_fresh": self.exit_quote_fresh,
                "exit_depth_contracts": self.exit_depth_contracts,
                "exit_depth_verified": self.exit_depth_verified,
                "entry_order_active": self.entry_order_active,
                "entry_liquidity_role": self.entry_liquidity_role,
                "entry_fee_cents": self.entry_fee_cents,
                "entry_cost_cents": self.entry_cost_cents,
                "entry_cost_source": self.entry_cost_source,
                "mark_change_cents": self.mark_change_cents,
                "time_to_close_hours": self.time_to_close_hours,
                "fee_cents_per_contract": self.fee_cents_per_contract,
                "hold_value_upper_cents": self.hold_value_upper_cents,
                "exit_advantage_cents": self.exit_advantage_cents,
            },
            created_at=self.advisory_created_at,
        )


def _parse_utc(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _optional_nonnegative_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _exit_bid_depth(market: MarketView, side: str) -> int | None:
    """Return top-bid quantity only when the snapshot explicitly carries it."""
    raw = market.raw if isinstance(market.raw, dict) else {}
    for key in (f"{side}_bid_size", f"{side}_bid_count", f"{side}_bid_quantity"):
        value = raw.get(key)
        try:
            depth = int(float(value))
        except (TypeError, ValueError):
            continue
        if depth >= 0:
            return depth
    return None


def advise_exit(
    position: dict[str, Any],
    market: MarketView,
    forecast: Forecast,
    *,
    min_advantage_cents: float = MIN_EXIT_ADVANTAGE_CENTS,
    confidence_sigmas: float = EXIT_CONFIDENCE_SIGMAS,
    now: datetime | None = None,
) -> ExitAdvisory | None:
    """Return conservative HOLD/EXIT research advice for a witnessed fill.

    ``EXIT`` is an observational label, never an executable instruction. An
    active remainder on a partially filled entry and an un-timestamped/stale
    quote force HOLD because an exit could otherwise race a still-live buy or
    rely on a book that no longer existed.
    """
    filled = int(position.get("filled_count", 0) or 0)
    if filled <= 0:
        return None
    side = str(position.get("side", "")).lower()
    if side not in {"yes", "no"}:
        return None

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    advisory_created_at = now.isoformat()
    decision_id = str(position.get("decision_id", ""))
    ticker = str(position.get("market_ticker", market.ticker))
    entry_price = int(
        position.get("fill_price_cents") or position.get("price_cents", 0) or 0
    )
    entry_order_active = bool(position.get("order_active", False))
    entry_role = str(position.get("liquidity_role") or "unknown").lower()
    if entry_role not in {"maker", "taker", "mixed"}:
        entry_role = "unknown"
    entry_fee = _optional_nonnegative_int(position.get("execution_fee_cents"))
    entry_cost = _optional_nonnegative_int(position.get("fill_cost_cents"))
    if entry_cost is not None:
        entry_cost_source = "witnessed_fill_cost"
    elif entry_fee is not None:
        entry_cost = entry_price * filled + entry_fee
        entry_cost_source = "witnessed_fee_plus_fill_price"
    else:
        entry_cost_source = "unverified"

    quote_time = _parse_utc(market.fetched_at)
    quote_age = (
        None
        if quote_time is None or quote_time > now
        else (now - quote_time).total_seconds()
    )
    quote_fresh = quote_age is not None and quote_age <= MAX_EXIT_QUOTE_AGE_SECONDS
    exit_depth = _exit_bid_depth(market, side)
    depth_verified = exit_depth is not None and exit_depth >= filled
    close_time = _parse_utc(market.close_time)
    time_to_close = None if close_time is None else (
        close_time - now
    ).total_seconds() / 3600.0

    base = {
        "decision_id": decision_id,
        "market_ticker": ticker,
        "side": side,
        "probability_yes": forecast.probability_yes,
        "forecast_uncertainty": forecast.uncertainty,
        "filled_count": filled,
        "entry_price_cents": entry_price,
        "advisory_created_at": advisory_created_at,
        "exit_quote_observed_at": market.fetched_at,
        "exit_quote_age_seconds": (
            round(quote_age, 3) if quote_age is not None else None
        ),
        "exit_quote_fresh": quote_fresh,
        "exit_depth_contracts": exit_depth,
        "exit_depth_verified": depth_verified,
        "entry_order_active": entry_order_active,
        "entry_liquidity_role": entry_role,
        "entry_fee_cents": entry_fee,
        "entry_cost_cents": entry_cost,
        "entry_cost_source": entry_cost_source,
        "time_to_close_hours": (
            round(time_to_close, 4) if time_to_close is not None else None
        ),
    }
    exit_bid = market.yes_bid if side == "yes" else market.no_bid
    if exit_bid is None or not 1 <= int(exit_bid) <= 99:
        return ExitAdvisory(
            **base,
            action="HOLD",
            executable_exit_cents=None,
            mark_change_cents=None,
            fee_cents_per_contract=None,
            hold_value_upper_cents=None,
            exit_advantage_cents=None,
            reason="no quoted exit bid",
        )

    exit_bid = int(exit_bid)
    total_fee = kalshi_taker_fee_cents(exit_bid, filled, ticker)
    fee_per_contract = total_fee / filled
    exit_proceeds = exit_bid - fee_per_contract
    win_probability = (
        forecast.probability_yes if side == "yes" else 1.0 - forecast.probability_yes
    )
    hold_upper_probability = min(
        0.995,
        max(0.005, win_probability + confidence_sigmas * forecast.uncertainty),
    )
    hold_upper = hold_upper_probability * 100.0
    advantage = exit_proceeds - hold_upper
    evidence_blocker = None
    if entry_order_active:
        evidence_blocker = "entry order remains active"
    elif not quote_fresh:
        evidence_blocker = "exit quote freshness is unverified"
    action = (
        "EXIT"
        if advantage >= min_advantage_cents and evidence_blocker is None
        else "HOLD"
    )
    reason = (
        f"quoted exit beats uncertainty-adjusted hold by {advantage:.1f}c"
        if action == "EXIT"
        else (
            evidence_blocker
            or f"exit advantage {advantage:.1f}c below {min_advantage_cents:.1f}c threshold"
        )
    )
    return ExitAdvisory(
        **base,
        action=action,
        executable_exit_cents=exit_bid,
        mark_change_cents=exit_bid - entry_price,
        fee_cents_per_contract=round(fee_per_contract, 4),
        hold_value_upper_cents=round(hold_upper, 4),
        exit_advantage_cents=round(advantage, 4),
        reason=reason,
    )


def build_exit_advisories(
    positions: Iterable[dict[str, Any]],
    scored: Iterable[tuple[MarketView, Forecast]],
) -> list[ExitAdvisory]:
    views = {market.ticker: (market, forecast) for market, forecast in scored}
    advisories: list[ExitAdvisory] = []
    for position in positions:
        pair = views.get(str(position.get("market_ticker", "")))
        if pair is None:
            continue
        advisory = advise_exit(position, pair[0], pair[1])
        if advisory is not None:
            advisories.append(advisory)
    return advisories


def write_exit_advisory_artifact(
    positions: Iterable[dict[str, Any]],
    scored: Iterable[tuple[MarketView, Forecast]],
    path: Path = EXIT_ARTIFACT_PATH,
) -> list[ExitAdvisory]:
    advisories = build_exit_advisories(positions, scored)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "exit_advisor_v2",
        "mode": "shadow_advisory_only",
        "live_execution_enabled": False,
        "quote_semantics": "displayed_bid_not_a_fill",
        "depth_required_for_execution_claim": True,
        "count": len(advisories),
        "exit_count": sum(1 for row in advisories if row.action == "EXIT"),
        "depth_verified_exit_count": sum(
            1 for row in advisories if row.action == "EXIT" and row.exit_depth_verified
        ),
        "advisories": [asdict(row) for row in advisories],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    return advisories


__all__ = [
    "EXIT_ARTIFACT_PATH",
    "ExitAdvisory",
    "advise_exit",
    "build_exit_advisories",
    "write_exit_advisory_artifact",
]
