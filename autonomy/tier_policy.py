"""Conservative, executable-value tiers for Dummy's daily betting guide.

The legacy board labelled markets from the fused probability's distance from
50%.  That made a 99% forecast an ``A`` even when the venue already priced the
same outcome at 99 cents.  These tiers instead describe *actionable quoted
value*: the best available side's model probability minus its ask and a
conservative one-contract taker fee, subject to uncertainty and scarcity
guards.

Tiers remain display/research metadata.  They do not grant execution,
promotion, sizing, or live-submit authority.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Iterable

from autonomy.correlation import group_key
from autonomy.fees import kalshi_taker_fee_cents
from autonomy.sports_markets import spec_for
from autonomy.taxonomy import prediction_subject

TIER_POLICY_VERSION = "executable_value_v5"

# A is deliberately exceptional.  The thresholds are point-estimate hurdles,
# not claims of statistical certainty; forward outcome tables track whether
# they prove durable.  Taker fees make the guide conservative even when the
# execution path may later earn a maker fill.
TIER_RULES: tuple[tuple[str, float, float], ...] = (
    ("A", 0.040, 0.12),
    ("B", 0.020, 0.18),
    ("C", 0.010, 0.25),
)
A_MAX_PER_SCOPE = 5
A_MAX_PER_EVENT = 1
MAX_QUOTE_AGE_SECONDS = 15 * 60.0
MAX_QUOTE_FUTURE_SKEW_SECONDS = 5.0
TIER_POLICY_SPEC = {
    "version": TIER_POLICY_VERSION,
    # Report artifacts must be JSON-native so write/read round trips preserve
    # exact equality. TIER_RULES stays immutable for policy evaluation.
    "rules": [list(rule) for rule in TIER_RULES],
    "a_max_per_scope": A_MAX_PER_SCOPE,
    "a_max_per_event": A_MAX_PER_EVENT,
    "cost_model": "quoted_ask_plus_one_contract_kalshi_taker_fee",
    "executable_depth_rule": (
        "valid_two_sided_selected_side_quote_and_either_positive_bid_and_ask_"
        "size_fp_or_positive_legacy_liquidity"
    ),
    "max_quote_age_seconds": MAX_QUOTE_AGE_SECONDS,
    "max_quote_future_skew_seconds": MAX_QUOTE_FUTURE_SKEW_SECONDS,
    "crypto_horizons_hours": {"hourly": 1.5, "daily": 36.0, "weekly": 240.0},
    "snapshot_schema_version": 4,
    "snapshot_bindings": [
        "ticker",
        "uncertainty",
        "quote_time",
        "close_time",
        "market_status",
        "fee_math",
        "reported_liquidity",
        "selected_side_bid",
        "selected_side_bid_size_fp",
        "selected_side_ask_size_fp",
        "effective_depth",
        "depth_source",
        "scope",
        "event",
    ],
}
TIER_POLICY_SHA256 = hashlib.sha256(
    json.dumps(TIER_POLICY_SPEC, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def _tier_snapshot_digest(values: dict[str, Any]) -> str:
    """Digest exactly the frozen tier namespace, including the tier label."""
    tier_fields = {
        key: value for key, value in values.items()
        if key == "tier" or (
            key.startswith("tier_")
            and key not in {"tier_snapshot_sha256", "tier_display_bucket"}
        )
    }
    return hashlib.sha256(
        json.dumps(tier_fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class TierAssessment:
    """Immutable point-in-time tier evidence for one market forecast."""

    ticker: str
    policy_version: str = TIER_POLICY_VERSION
    tier: str | None = None
    base_tier: str | None = None
    side: str | None = None
    entry_price_cents: int | None = None
    modeled_fee_cents: int | None = None
    gross_executable_edge: float | None = None
    after_fee_edge: float | None = None
    uncertainty: float | None = None
    scope: str = "OTHER"
    market_type: str = "market"
    horizon_phase: str = "unknown"
    assessed_at: str | None = None
    quote_fetched_at: str | None = None
    quote_age_seconds: float | None = None
    close_time: str | None = None
    market_status: str | None = None
    liquidity: float | None = None
    selected_bid_cents: int | None = None
    selected_bid_size_fp: float | None = None
    selected_ask_size_fp: float | None = None
    effective_depth: float | None = None
    depth_source: str | None = None
    event_key: str = ""
    reason: str = "not_assessed"
    scarcity_demoted: bool = False

    @property
    def score(self) -> float | None:
        """Transparent ranking score: after-fee edge, not a probability."""
        return self.after_fee_edge

    def feature_fields(self) -> dict[str, Any]:
        """JSON-safe fields persisted with the fused forecast of record."""
        fields = {
            "tier_policy_version": self.policy_version,
            "tier_policy_sha256": TIER_POLICY_SHA256,
            "tier_ticker": self.ticker,
            "tier": self.tier,
            "tier_base": self.base_tier,
            "tier_side": self.side,
            "tier_entry_price_cents": self.entry_price_cents,
            "tier_modeled_fee_cents": self.modeled_fee_cents,
            "tier_gross_executable_edge": _rounded(self.gross_executable_edge),
            "tier_after_fee_edge": _rounded(self.after_fee_edge),
            "tier_uncertainty": _rounded(self.uncertainty),
            "tier_score": _rounded(self.score),
            "tier_scope": self.scope,
            "tier_market_type": self.market_type,
            "tier_horizon_phase": self.horizon_phase,
            "tier_assessed_at": self.assessed_at,
            "tier_quote_fetched_at": self.quote_fetched_at,
            "tier_quote_age_seconds": _rounded(self.quote_age_seconds),
            "tier_close_time": self.close_time,
            "tier_market_status": self.market_status,
            "tier_liquidity": _rounded(self.liquidity),
            "tier_selected_bid_cents": self.selected_bid_cents,
            "tier_selected_bid_size_fp": _rounded(self.selected_bid_size_fp),
            "tier_selected_ask_size_fp": _rounded(self.selected_ask_size_fp),
            "tier_effective_depth": _rounded(self.effective_depth),
            "tier_depth_source": self.depth_source,
            "tier_event_key": self.event_key,
            "tier_reason": self.reason,
            "tier_scarcity_demoted": self.scarcity_demoted,
        }
        fields["tier_snapshot_sha256"] = _tier_snapshot_digest(fields)
        return fields


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(float(value), 6)


def _valid_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _valid_ask(value: Any) -> int | None:
    parsed = _valid_number(value)
    if parsed is None or not parsed.is_integer():
        return None
    ask = int(parsed)
    return ask if 1 <= ask <= 99 else None


def _positive_size_fp(value: Any) -> float | None:
    """Parse a finite, strictly positive Kalshi fixed-point quote size."""
    parsed = _valid_number(value)
    return parsed if parsed is not None and parsed > 0.0 else None


def _paired_quote_sizes(
    raw: dict[str, Any],
    first_key: str,
    inverse_key: str,
) -> tuple[float | None, float | None]:
    """Normalize the two names for one binary-contract queue.

    A YES bid is the same queue as a NO ask, and a YES ask is the same queue
    as a NO bid.  Kalshi's current market schema reports only the YES-named
    ``*_size_fp`` fields.  If both names are ever reported, disagreement is
    treated as invalid rather than choosing one.
    """
    first_present = first_key in raw and raw.get(first_key) is not None
    inverse_present = inverse_key in raw and raw.get(inverse_key) is not None
    first = _positive_size_fp(raw.get(first_key)) if first_present else None
    inverse = _positive_size_fp(raw.get(inverse_key)) if inverse_present else None
    if first_present and inverse_present:
        if (
            first is None
            or inverse is None
            or not math.isclose(first, inverse, rel_tol=0.0, abs_tol=1e-6)
        ):
            return None, None
        return first, inverse
    if first_present:
        return (first, first) if first is not None else (None, None)
    if inverse_present:
        return (inverse, inverse) if inverse is not None else (None, None)
    return None, None


def normalized_quote_sizes(market: Any) -> dict[str, float | None]:
    """Return fail-closed side-specific sizes from ``MarketView.raw``.

    The raw payload remains the source of truth; no liquidity or volume proxy
    is converted into a quote size.  Returned values are JSON-safe numbers and
    keep Kalshi's ``*_size_fp`` names for transparent display/replay binding.
    """
    raw = getattr(market, "raw", None)
    raw = raw if isinstance(raw, dict) else {}
    yes_bid, no_ask = _paired_quote_sizes(
        raw, "yes_bid_size_fp", "no_ask_size_fp"
    )
    yes_ask, no_bid = _paired_quote_sizes(
        raw, "yes_ask_size_fp", "no_bid_size_fp"
    )
    return {
        "yes_bid_size_fp": yes_bid,
        "yes_ask_size_fp": yes_ask,
        "no_bid_size_fp": no_bid,
        "no_ask_size_fp": no_ask,
    }


def _depth_evidence(
    market: Any,
    side: str,
    liquidity: float | None,
) -> tuple[float | None, float | None, float | None, str | None]:
    """Bind selected-side depth, preferring the current quote-size schema."""
    sizes = normalized_quote_sizes(market)
    bid_size = _positive_size_fp(sizes.get(f"{side}_bid_size_fp"))
    ask_size = _positive_size_fp(sizes.get(f"{side}_ask_size_fp"))
    if bid_size is not None and ask_size is not None:
        return bid_size, ask_size, min(bid_size, ask_size), "quote_sizes_fp"
    if liquidity is not None and liquidity > 0.0:
        # Legacy liquidity is retained only as an explicitly named fallback.
        # It is not represented as a per-side quote size.
        return None, None, liquidity, "legacy_liquidity"
    return None, None, None, None


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _scope(ticker: str) -> str:
    spec = spec_for(ticker)
    if spec is not None:
        return str(spec.league or "OTHER").upper()
    return str(prediction_subject(ticker) or "OTHER").upper()


def _dimensions(
    ticker: str,
    hours_to_close: float | None = None,
) -> tuple[str, str]:
    spec = spec_for(ticker)
    if spec is not None:
        market_type = (
            f"prop_{spec.stat}" if spec.is_prop and spec.stat else str(spec.market_type)
        )
        return market_type, str(spec.segment or "full")
    series = ticker.split("-", 1)[0].upper()
    for suffix, horizon in (
        ("15M", "15m"), ("1H", "hourly"), ("DAILY", "daily"),
        ("WEEKLY", "weekly"), ("D", "daily"), ("W", "weekly"),
    ):
        if series.endswith(suffix):
            return "market", horizon
    if hours_to_close is None or not math.isfinite(hours_to_close):
        return "market", "unknown"
    if hours_to_close <= 1.5:
        return "market", "hourly"
    if hours_to_close <= 36.0:
        return "market", "daily"
    if hours_to_close <= 240.0:
        return "market", "weekly"
    return "market", "longer"


def _tier_for(edge: float, uncertainty: float) -> str | None:
    # A tiny epsilon prevents a binary floating-point representation from
    # failing a threshold that is exactly met in decimal inputs.
    for label, min_edge, max_uncertainty in TIER_RULES:
        if edge + 1e-12 >= min_edge and uncertainty <= max_uncertainty + 1e-12:
            return label
    return None


def assess_market_tier(
    market: Any,
    forecast: Any,
    *,
    now: datetime | None = None,
) -> TierAssessment:
    """Classify one forecast using quotes actually available at assessment.

    Both YES and NO asks are evaluated independently.  A missing or malformed
    quote cannot receive a letter tier.  This avoids converting a midpoint or
    a theoretical model disagreement into a supposedly executable bet.
    """
    assessed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    ticker = str(getattr(market, "ticker", "") or "")
    scope = _scope(ticker)
    fetched_raw = getattr(market, "fetched_at", None)
    fetched = _parse_datetime(fetched_raw)
    close_raw = getattr(market, "close_time", None)
    close = _parse_datetime(close_raw)
    hours_to_close = (
        max(0.0, (close - fetched).total_seconds() / 3600.0)
        if close is not None and fetched is not None else None
    )
    market_type, horizon_phase = _dimensions(ticker, hours_to_close)
    event = group_key(ticker)
    probability_yes = _valid_number(getattr(forecast, "probability_yes", None))
    uncertainty = _valid_number(getattr(forecast, "uncertainty", None))
    base = TierAssessment(
        ticker=ticker,
        uncertainty=uncertainty,
        scope=scope,
        market_type=market_type,
        horizon_phase=horizon_phase,
        assessed_at=assessed.isoformat(),
        quote_fetched_at=fetched.isoformat() if fetched is not None else None,
        quote_age_seconds=(
            (assessed - fetched).total_seconds() if fetched is not None else None
        ),
        close_time=close.isoformat() if close is not None else None,
        market_status=str(getattr(market, "status", "") or "") or None,
        event_key=event,
    )
    if probability_yes is None or not 0.0 <= probability_yes <= 1.0:
        return replace(base, reason="invalid_probability")
    if uncertainty is None or not 0.0 <= uncertainty <= 0.5:
        return replace(base, reason="invalid_uncertainty")
    if fetched is None:
        return replace(base, reason="missing_quote_timestamp")
    quote_age = (assessed - fetched).total_seconds()
    if quote_age < -MAX_QUOTE_FUTURE_SKEW_SECONDS:
        return replace(base, reason="future_quote_timestamp")
    if quote_age > MAX_QUOTE_AGE_SECONDS:
        return replace(base, reason="stale_quote")
    if close is None:
        return replace(base, reason="missing_close_time")
    if close <= assessed:
        return replace(base, reason="market_closed")
    status = str(getattr(market, "status", "") or "").strip().lower()
    if not status:
        return replace(base, reason="missing_market_status")
    if status not in {"open", "active", "trading"}:
        return replace(base, reason="market_not_open")
    liquidity = _valid_number(getattr(market, "liquidity", None))

    candidates: list[
        tuple[
            float,
            float,
            str,
            int,
            int,
            int,
            float | None,
            float | None,
            float,
            str,
        ]
    ] = []
    for side, bid_raw, ask_raw, win_probability in (
        (
            "yes",
            getattr(market, "yes_bid", None),
            getattr(market, "yes_ask", None),
            probability_yes,
        ),
        (
            "no",
            getattr(market, "no_bid", None),
            getattr(market, "no_ask", None),
            1.0 - probability_yes,
        ),
    ):
        bid = _valid_ask(bid_raw)
        ask = _valid_ask(ask_raw)
        if bid is None or ask is None or bid >= ask:
            continue
        bid_size, ask_size, effective_depth, depth_source = _depth_evidence(
            market, side, liquidity
        )
        if effective_depth is None or depth_source is None:
            continue
        fee = kalshi_taker_fee_cents(ask, 1, ticker)
        gross = win_probability - ask / 100.0
        net = gross - fee / 100.0
        # Lower ask wins exact net ties, then a stable side string makes the
        # result deterministic across runs.
        candidates.append(
            (
                net,
                gross,
                side,
                ask,
                fee,
                bid,
                bid_size,
                ask_size,
                effective_depth,
                depth_source,
            )
        )
    if not candidates:
        return replace(base, reason="no_executable_depth", liquidity=liquidity)

    (
        net,
        gross,
        side,
        ask,
        fee,
        bid,
        bid_size,
        ask_size,
        effective_depth,
        depth_source,
    ) = max(
        candidates,
        key=lambda row: (row[0], row[1], -row[3], row[2]),
    )
    label = _tier_for(net, uncertainty)
    if label is None:
        reason = "below_c_after_fee_edge"
        if net >= TIER_RULES[-1][1]:
            reason = "uncertainty_above_tier_gate"
    else:
        reason = f"meets_{label.lower()}_edge_and_uncertainty"
    return replace(
        base,
        tier=label,
        base_tier=label,
        side=side,
        entry_price_cents=ask,
        modeled_fee_cents=fee,
        liquidity=liquidity,
        selected_bid_cents=bid,
        selected_bid_size_fp=bid_size,
        selected_ask_size_fp=ask_size,
        effective_depth=effective_depth,
        depth_source=depth_source,
        gross_executable_edge=gross,
        after_fee_edge=net,
        reason=reason,
    )


def assign_cycle_tiers(
    scored: Iterable[tuple[Any, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, TierAssessment]:
    """Assess a cycle and enforce A-tier scarcity deterministically.

    At most one A survives per correlated event/expiry and at most five per
    league/asset scope.  Overflow A candidates become B rather than vanishing:
    every base-A candidate necessarily clears B's numerical hurdle.
    """
    assessed_at = now or datetime.now(timezone.utc)
    assessments = [
        assess_market_tier(market, forecast, now=assessed_at)
        for market, forecast in scored
    ]
    a_candidates = sorted(
        (row for row in assessments if row.tier == "A"),
        key=lambda row: (
            -(row.after_fee_edge if row.after_fee_edge is not None else -math.inf),
            row.uncertainty if row.uncertainty is not None else math.inf,
            row.ticker,
        ),
    )
    event_counts: dict[str, int] = {}
    scope_counts: dict[str, int] = {}
    demoted: set[str] = set()
    for row in a_candidates:
        scope_count = scope_counts.get(row.scope, 0)
        event_count = event_counts.get(row.event_key, 0)
        if event_count >= A_MAX_PER_EVENT or scope_count >= A_MAX_PER_SCOPE:
            demoted.add(row.ticker)
            continue
        event_counts[row.event_key] = event_count + 1
        scope_counts[row.scope] = scope_count + 1

    result: dict[str, TierAssessment] = {}
    for row in assessments:
        if row.ticker in demoted and row.tier == "A":
            row = replace(
                row,
                tier="B",
                reason="a_scarcity_cap_demoted_to_b",
                scarcity_demoted=True,
            )
        result[row.ticker] = row
    return result


def assessment_from_features(ticker: str, features: dict[str, Any]) -> TierAssessment:
    """Restore current-policy metadata; legacy rows stay unclassified."""
    if not tier_snapshot_is_valid(features, ticker=ticker):
        return TierAssessment(
            ticker=ticker,
            policy_version="unattributed",
            scope=_scope(ticker),
            market_type=_dimensions(ticker)[0],
            horizon_phase=_dimensions(ticker)[1],
            event_key=group_key(ticker),
            reason="legacy_missing_or_invalid_tier_snapshot",
        )
    tier = features.get("tier")
    if tier not in {None, "A", "B", "C"}:
        tier = None
    side = features.get("tier_side")
    if side not in {None, "yes", "no"}:
        side = None
    return TierAssessment(
        ticker=ticker,
        tier=tier,
        base_tier=features.get("tier_base") if features.get("tier_base") in {None, "A", "B", "C"} else None,
        side=side,
        entry_price_cents=_valid_ask(features.get("tier_entry_price_cents")),
        modeled_fee_cents=_int_or_none(features.get("tier_modeled_fee_cents")),
        gross_executable_edge=_valid_number(features.get("tier_gross_executable_edge")),
        after_fee_edge=_valid_number(features.get("tier_after_fee_edge")),
        uncertainty=_valid_number(features.get("tier_uncertainty")),
        scope=str(features.get("tier_scope") or _scope(ticker)),
        market_type=str(features.get("tier_market_type") or _dimensions(ticker)[0]),
        horizon_phase=str(
            features.get("tier_horizon_phase") or _dimensions(ticker)[1]
        ),
        assessed_at=(
            str(features.get("tier_assessed_at"))
            if features.get("tier_assessed_at") else None
        ),
        quote_fetched_at=(
            str(features.get("tier_quote_fetched_at"))
            if features.get("tier_quote_fetched_at") else None
        ),
        quote_age_seconds=_valid_number(features.get("tier_quote_age_seconds")),
        close_time=(
            str(features.get("tier_close_time"))
            if features.get("tier_close_time") else None
        ),
        market_status=(
            str(features.get("tier_market_status"))
            if features.get("tier_market_status") else None
        ),
        liquidity=_valid_number(features.get("tier_liquidity")),
        selected_bid_cents=_valid_ask(
            features.get("tier_selected_bid_cents")
        ),
        selected_bid_size_fp=_positive_size_fp(
            features.get("tier_selected_bid_size_fp")
        ),
        selected_ask_size_fp=_positive_size_fp(
            features.get("tier_selected_ask_size_fp")
        ),
        effective_depth=_positive_size_fp(features.get("tier_effective_depth")),
        depth_source=(
            str(features.get("tier_depth_source"))
            if features.get("tier_depth_source") else None
        ),
        event_key=str(features.get("tier_event_key") or group_key(ticker)),
        reason=str(features.get("tier_reason") or "persisted_tier"),
        scarcity_demoted=bool(features.get("tier_scarcity_demoted", False)),
    )


def _int_or_none(value: Any) -> int | None:
    parsed = _valid_number(value)
    return int(parsed) if parsed is not None and parsed.is_integer() else None


# Every numeric a consumer may do tier arithmetic on.  A snapshot that names a
# selected side is claiming executable quoted value, so all of them must be
# present and finite for that claim to be checkable.
_EXECUTABLE_NUMERIC_FIELDS = (
    "tier_entry_price_cents",
    "tier_modeled_fee_cents",
    "tier_gross_executable_edge",
    "tier_after_fee_edge",
    "tier_score",
    "tier_uncertainty",
)


def tier_snapshot_is_executable(features: dict[str, Any]) -> bool:
    """Whether a snapshot carries a selected side and complete, finite fee math.

    ``tier_snapshot_is_valid`` admits two lawful shapes.  An *executable*
    snapshot names a side and every number its tier claim was derived from.  A
    ``no_executable_depth`` snapshot is an equally truthful record that no
    two-sided quote existed, and its contract *requires* the executable fields
    to be ``None`` — the board relies on that shape to display an honest
    ``UNATTRIBUTED / no_executable_depth`` row rather than a fabricated one.

    Consumers that do price arithmetic must therefore ask which shape they hold
    before dereferencing.  Skipping that question is what killed live cycles:
    ``float(snapshot["tier_entry_price_cents"])`` on the second shape raises
    TypeError, so a display-only classification took the decide/execute stages
    down with it.
    """
    if not isinstance(features, dict):
        return False
    if features.get("tier_side") not in {"yes", "no"}:
        return False
    if _valid_ask(features.get("tier_entry_price_cents")) is None:
        return False
    return all(
        _valid_number(features.get(key)) is not None
        for key in _EXECUTABLE_NUMERIC_FIELDS
    )


def tier_snapshot_is_valid(
    features: dict[str, Any],
    *,
    ticker: str | None = None,
) -> bool:
    """Verify digest, identity, timestamps, fee math, and tier semantics.

    The digest is tamper evidence, not authority: anyone can recompute a hash.
    A snapshot is current evidence only when its contents also reproduce the
    exact policy result and bind the target that is being graded or displayed.
    """
    if (
        not isinstance(features, dict)
        or features.get("tier_policy_version") != TIER_POLICY_VERSION
        or features.get("tier_policy_sha256") != TIER_POLICY_SHA256
    ):
        return False
    claimed = features.get("tier_snapshot_sha256")
    if not isinstance(claimed, str) or len(claimed) != 64:
        return False
    if _tier_snapshot_digest(features) != claimed:
        return False

    bound_ticker = str(features.get("tier_ticker") or "").strip()
    if not bound_ticker or (ticker is not None and bound_ticker != str(ticker)):
        return False
    uncertainty = _valid_number(features.get("tier_uncertainty"))
    if uncertainty is None or not 0.0 <= uncertainty <= 0.5:
        return False
    assessed = _parse_datetime(features.get("tier_assessed_at"))
    quoted = _parse_datetime(features.get("tier_quote_fetched_at"))
    close = _parse_datetime(features.get("tier_close_time"))
    claimed_age = _valid_number(features.get("tier_quote_age_seconds"))
    if None in {assessed, quoted, close, claimed_age}:
        return False
    observed_age = (assessed - quoted).total_seconds()
    if (
        observed_age < -MAX_QUOTE_FUTURE_SKEW_SECONDS
        or observed_age > MAX_QUOTE_AGE_SECONDS
        or abs(observed_age - float(claimed_age)) > 0.01
        or close <= assessed
    ):
        return False
    status = str(features.get("tier_market_status") or "").strip().lower()
    if status not in {"open", "active", "trading"}:
        return False
    if str(features.get("tier_event_key") or "") != group_key(bound_ticker):
        return False
    if str(features.get("tier_scope") or "") != _scope(bound_ticker):
        return False
    hours_to_close = (close - quoted).total_seconds() / 3600.0
    expected_market_type, expected_horizon = _dimensions(
        bound_ticker, hours_to_close
    )
    if (
        str(features.get("tier_market_type") or "") != expected_market_type
        or str(features.get("tier_horizon_phase") or "") != expected_horizon
    ):
        return False

    # Shape guard, ahead of the per-field checks below: a snapshot that names a
    # selected side must supply every number its own tier claim is derived
    # from.  The individual checks further down already reject each missing
    # field, but only as a side effect of arithmetic they happen to perform;
    # stating the invariant by name keeps "claims a side" and "is safe to do
    # float() arithmetic on" the same predicate for every consumer.
    if (
        features.get("tier_side") is not None
        and not tier_snapshot_is_executable(features)
    ):
        return False

    reason = str(features.get("tier_reason") or "")
    if reason == "no_executable_depth":
        return (
            features.get("tier") is None
            and features.get("tier_base") is None
            and features.get("tier_side") is None
            and features.get("tier_entry_price_cents") is None
            and features.get("tier_modeled_fee_cents") is None
            and features.get("tier_gross_executable_edge") is None
            and features.get("tier_after_fee_edge") is None
            and features.get("tier_score") is None
            and features.get("tier_selected_bid_cents") is None
            and features.get("tier_selected_bid_size_fp") is None
            and features.get("tier_selected_ask_size_fp") is None
            and features.get("tier_effective_depth") is None
            and features.get("tier_depth_source") is None
            and features.get("tier_scarcity_demoted") is False
        )

    side = features.get("tier_side")
    liquidity = _valid_number(features.get("tier_liquidity"))
    bid = _valid_ask(features.get("tier_selected_bid_cents"))
    bid_size = _positive_size_fp(features.get("tier_selected_bid_size_fp"))
    ask_size = _positive_size_fp(features.get("tier_selected_ask_size_fp"))
    effective_depth = _positive_size_fp(features.get("tier_effective_depth"))
    depth_source = features.get("tier_depth_source")
    ask = _valid_ask(features.get("tier_entry_price_cents"))
    fee = _int_or_none(features.get("tier_modeled_fee_cents"))
    gross = _valid_number(features.get("tier_gross_executable_edge"))
    net = _valid_number(features.get("tier_after_fee_edge"))
    score = _valid_number(features.get("tier_score"))
    if (
        side not in {"yes", "no"}
        or bid is None
        or ask is None
        or bid >= ask
        or fee is None
        or gross is None
        or net is None
        or score is None
        or not -0.99 <= gross <= 0.99
        or not 0.0 <= gross + ask / 100.0 <= 1.0
        or fee != kalshi_taker_fee_cents(ask, 1, bound_ticker)
        or abs(net - (gross - fee / 100.0)) > 1e-6
        or abs(score - net) > 1e-6
    ):
        return False
    if depth_source == "quote_sizes_fp":
        if (
            bid_size is None
            or ask_size is None
            or effective_depth is None
            or not math.isclose(
                effective_depth,
                min(bid_size, ask_size),
                rel_tol=0.0,
                abs_tol=1e-6,
            )
        ):
            return False
    elif depth_source == "legacy_liquidity":
        if (
            liquidity is None
            or liquidity <= 0.0
            or bid_size is not None
            or ask_size is not None
            or effective_depth is None
            or not math.isclose(
                effective_depth, liquidity, rel_tol=0.0, abs_tol=1e-6
            )
        ):
            return False
    else:
        return False

    expected_base = _tier_for(net, uncertainty)
    tier = features.get("tier")
    base = features.get("tier_base")
    demoted = features.get("tier_scarcity_demoted")
    if not isinstance(demoted, bool):
        return False
    if expected_base is None:
        expected_reason = (
            "uncertainty_above_tier_gate"
            if net >= TIER_RULES[-1][1]
            else "below_c_after_fee_edge"
        )
        return (
            tier is None
            and base is None
            and demoted is False
            and reason == expected_reason
        )
    if expected_base == "A" and demoted:
        return (
            tier == "B"
            and base == "A"
            and reason == "a_scarcity_cap_demoted_to_b"
        )
    return (
        demoted is False
        and tier == expected_base
        and base == expected_base
        and reason == f"meets_{expected_base.lower()}_edge_and_uncertainty"
    )
