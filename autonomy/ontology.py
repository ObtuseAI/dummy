"""Typed core objects for the autonomy loop."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Vertical(str, Enum):
    WEATHER = "WEATHER"
    CRYPTO = "CRYPTO"
    SPORTS = "SPORTS"
    COMMODITIES = "COMMODITIES"
    ECON = "ECON"
    OTHER = "OTHER"


class SessionMode(str, Enum):
    SHADOW = "SHADOW"  # full pipeline, orders recorded in shadow book only
    LIVE = "LIVE"  # orders routed through the hardened Kalshi adapter


class Stage(int, Enum):
    """Risk stage ladder; advancement requires explicit human promotion."""

    SHADOW_ONLY = 0
    CANARY = 1  # tiny notional, few markets
    RAMP = 2  # moderate notional, more markets
    CRUISE = 3  # full risk-brain budgets


class DecisionAction(str, Enum):
    BUY_YES = "BUY_YES"
    BUY_NO = "BUY_NO"
    ABSTAIN = "ABSTAIN"


class OutcomeKind(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    BLOCKED_LOCAL = "BLOCKED_LOCAL"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    SETTLED_WIN = "SETTLED_WIN"
    SETTLED_LOSS = "SETTLED_LOSS"
    SHADOW = "SHADOW"


@dataclass(frozen=True)
class MarketView:
    """Normalized view of one live Kalshi market from the scanner."""

    ticker: str
    title: str
    vertical: Vertical
    status: str
    close_time: str
    yes_bid: int | None
    yes_ask: int | None
    no_bid: int | None
    no_ask: int | None
    volume: int
    liquidity: int
    tick_size: int = 1
    raw: dict[str, Any] = field(default_factory=dict)
    # UTC ISO-8601 moment this book snapshot was fetched from the venue. Stamped
    # by the scanner so the executor's stale-data gate can refuse to submit an
    # order against a book that has since gone stale. None => unknown freshness.
    fetched_at: str | None = None


@dataclass(frozen=True)
class Signal:
    """One source's probability opinion about one market."""

    source: str
    market_ticker: str
    probability_yes: float  # 0..1
    uncertainty: float  # stddev-like width, 0..0.5
    rationale: str
    features: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class Forecast:
    """Calibration-weighted fusion of signals for one market."""

    market_ticker: str
    probability_yes: float
    uncertainty: float
    sources_used: dict[str, float]  # source -> weight actually applied
    market_implied_yes: float | None
    edge_yes: float  # probability_yes - implied (fee-unadjusted)
    rationale: str
    # Independent "model view" (Wave-78): the challenger-INCLUSIVE fusion, i.e.
    # what our own models collectively think BEFORE the promotion ladder filters
    # unpromoted challengers out of the traded ``probability_yes``. Display-only:
    # surfaces an independent both-sides read + model-vs-market edge on every
    # market/coin, even for challengers that cannot yet move the traded number.
    # ``None`` when no independent (non-market_prior) source priced the market.
    model_probability_yes: float | None = None
    model_uncertainty: float | None = None
    model_sources: dict[str, float] | None = None


@dataclass(frozen=True)
class Decision:
    """A sized, priced intention produced by the allocator + risk brain."""

    decision_id: str
    market_ticker: str
    action: DecisionAction
    side: str  # "yes" | "no"
    price_cents: int
    count: int
    ev_cents_per_contract: float
    kelly_fraction: float
    notional_cents: int
    forecast: Forecast
    risk_snapshot: dict[str, Any]
    abstain_reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Immutable display/research classification captured when the decision was
    # produced.  It grants no execution authority and is intentionally
    # versioned so historical definitions are never silently relabelled.
    tier_label: str | None = None
    tier_policy_version: str | None = None
    tier_score: float | None = None
    tier_reason: str = ""
    tier_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradeOutcome:
    """What actually happened to a decision, with transport-witness truth."""

    decision_id: str
    market_ticker: str
    kind: OutcomeKind
    order_id: str | None
    fill_count: int
    fill_price_cents: int | None
    pnl_cents: int | None
    broker_contacted: bool
    detail: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
