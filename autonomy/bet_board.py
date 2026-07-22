"""The bet board (Wave-15): every market dummy currently prices, ranked.

Operator ask: "display dummy ranking every bet along with its decided
probability and edge percentages, sectioned by league and bet type."

Wave-14 made this a query: the brain records its FINAL fused probability as a
``fused_forecast`` ledger row for every scored market, carrying the
contemporaneous market-implied probability in features. The board is the
latest fused emission per still-open market inside a freshness window,
grouped (league, market type) via the series registry and ranked by the frozen,
fee-adjusted executable-value tier within each group plus one global top list.

Two paths, artifact-first (matching every other dashboard panel):

  * ``write_board_artifact`` -- the brain calls this at the end of each cycle
    with the in-memory (market, forecast) pairs it just scored, atomically
    writing ``runtime/autonomy/bet_board.json``. No DB involved: the cycle
    already holds every row, titles included, and the busy ledger (single
    writer, non-WAL) must never be contended for a display read.
  * ``read_board_artifact`` -- the dashboard-safe public reader. It never
    opens the ledger and labels fresh, stale, missing, and invalid artifacts.
  * ``assemble_bet_board`` -- non-request cold-start helper; serve the fresh
    artifact or fall back to a busy-tolerant read of the Wave-14
    ``fused_forecast`` ledger rows. Dashboard request handlers must not use it.

Display-only: nothing here feeds fusion, trust, promotion, or execution.
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.picks import FUSED_SOURCE
from autonomy.sports_markets import FULL, SPORTS_LEAGUES, series_of, spec_for
from autonomy.taxonomy import prediction_subject
from autonomy.target_policy import (
    is_data_only_target,
    is_equity_index_target,
    is_prediction_quarantined_target,
)

# A fused emission older than this no longer reflects a live opinion (the
# scanner re-prices continuously; anything stale usually means the market
# closed or left the watchlist).
FRESH_HOURS = 36.0

BOARD_PATH = Path("runtime/autonomy/bet_board.json")
# Public/UI-only overlay written by the bounded sports quote refresher.  The
# execution-facing vNext runtime deliberately continues to read ``BOARD_PATH``
# directly, so this artifact cannot acquire execution, promotion, or trust
# authority through a display refresh.
DISPLAY_BOARD_PATH = Path("runtime/autonomy/bet_board_display.json")
# Cycles run every ~10 minutes; an artifact older than this is explicitly
# stale. Dashboard request paths still serve it labelled and never scan the
# ledger; only the non-request cold-start helper may use a ledger fallback.
ARTIFACT_FRESH_SECONDS = 2 * 3600.0
ARTIFACT_FUTURE_SKEW_SECONDS = 5 * 60.0
# A cycle normally persists its tier assessments in well under a minute.  A
# wider allowance covers a temporarily slow ledger write without letting an
# old assessment acquire a new life merely because it was wrapped in a freshly
# dated board artifact.
MAX_ASSESSMENT_TO_BOARD_SECONDS = 5 * 60.0
_TIER_LABELS = ("A", "B", "C", "WATCH", "UNATTRIBUTED")


def _sports_roster_fields() -> dict[str, Any]:
    """Static navigation metadata, never evidence of a current listing."""
    return {
        "sports_leagues": list(SPORTS_LEAGUES),
        "sports_league_roster_kind": "year_round_navigation_not_current_listings",
    }


def _finite_number(value: Any) -> float | None:
    """Parse a finite JSON number while rejecting booleans."""
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _same_number(left: Any, right: Any, *, tolerance: float = 1e-9) -> bool:
    left_number = _finite_number(left)
    right_number = _finite_number(right)
    return (
        left_number is not None
        and right_number is not None
        and abs(left_number - right_number) <= tolerance
    )


def _same_optional_number(
    left: Any,
    right: Any,
    *,
    tolerance: float = 1e-9,
) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return _same_number(left, right, tolerance=tolerance)


def _same_integer(left: Any, right: Any) -> bool:
    left_number = _finite_number(left)
    right_number = _finite_number(right)
    return (
        left_number is not None
        and right_number is not None
        and left_number.is_integer()
        and right_number.is_integer()
        and int(left_number) == int(right_number)
    )


def _utc_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _visible_tier_snapshot_is_bound(row: dict[str, Any]) -> bool:
    """Bind a valid tier snapshot to every duplicated user-visible value.

    The tier namespace is self-hashed, but the display row around it is not.
    Without these checks a copied valid snapshot could label a different
    ticker, probability, quote, side, or edge as an A-tier opportunity.
    """
    from autonomy.tier_policy import tier_snapshot_is_valid

    ticker = str(row.get("ticker") or "")
    if not tier_snapshot_is_valid(row, ticker=ticker):
        return False

    probability = _finite_number(row.get("probability"))
    uncertainty = _finite_number(row.get("uncertainty"))
    entry = _finite_number(row.get("tier_entry_price_cents"))
    selected_bid = _finite_number(row.get("tier_selected_bid_cents"))
    liquidity = _finite_number(row.get("tier_liquidity"))
    selected_bid_size = _finite_number(row.get("tier_selected_bid_size_fp"))
    selected_ask_size = _finite_number(row.get("tier_selected_ask_size_fp"))
    effective_depth = _finite_number(row.get("tier_effective_depth"))
    depth_source = row.get("tier_depth_source")
    gross = _finite_number(row.get("tier_gross_executable_edge"))
    side = row.get("tier_side")
    if (
        probability is None
        or not 0.0 <= probability <= 1.0
        or uncertainty is None
        or not 0.0 <= uncertainty <= 0.5
        or entry is None
        or selected_bid is None
        or effective_depth is None
        or effective_depth <= 0.0
        or gross is None
        or side not in {"yes", "no"}
        or depth_source not in {"quote_sizes_fp", "legacy_liquidity"}
    ):
        return False

    implied_side_probability = gross + entry / 100.0
    expected_probability = (
        implied_side_probability if side == "yes" else 1.0 - implied_side_probability
    )
    # The public probability is written at four decimals while the signed
    # edge is written at six.  These tolerances cover only those two explicit
    # serialization roundings.
    if not _same_number(probability, expected_probability, tolerance=0.000051):
        return False
    if not _same_number(
        uncertainty, row.get("tier_uncertainty"), tolerance=0.000501
    ):
        return False

    selected_ask = row.get("yes_ask" if side == "yes" else "no_ask")
    visible_bid = row.get("yes_bid" if side == "yes" else "no_bid")
    if not _same_integer(selected_ask, entry):
        return False
    if not _same_integer(visible_bid, selected_bid) or selected_bid >= entry:
        return False
    if not _same_optional_number(
        row.get("liquidity"), row.get("tier_liquidity"), tolerance=0.000001
    ):
        return False
    if row.get("depth_source") != depth_source:
        return False
    if not _same_number(
        row.get("effective_depth"), effective_depth, tolerance=0.000001
    ):
        return False
    if not _same_optional_number(
        row.get("selected_bid_size_fp"),
        row.get("tier_selected_bid_size_fp"),
        tolerance=0.000001,
    ):
        return False
    if not _same_optional_number(
        row.get("selected_ask_size_fp"),
        row.get("tier_selected_ask_size_fp"),
        tolerance=0.000001,
    ):
        return False
    if depth_source == "quote_sizes_fp":
        if (
            selected_bid_size is None
            or selected_ask_size is None
            or not _same_number(
                row.get(f"{side}_bid_size_fp"),
                selected_bid_size,
                tolerance=0.000001,
            )
            or not _same_number(
                row.get(f"{side}_ask_size_fp"),
                selected_ask_size,
                tolerance=0.000001,
            )
        ):
            return False
    elif (
        liquidity is None
        or liquidity <= 0.0
        or selected_bid_size is not None
        or selected_ask_size is not None
    ):
        return False
    if not _same_integer(
        row.get("entry_price_cents"), row.get("tier_entry_price_cents")
    ):
        return False
    if not _same_integer(
        row.get("modeled_fee_cents"), row.get("tier_modeled_fee_cents")
    ):
        return False
    if not _same_number(
        row.get("gross_executable_edge"),
        row.get("tier_gross_executable_edge"),
    ):
        return False
    if not _same_number(
        row.get("after_fee_edge"), row.get("tier_after_fee_edge")
    ):
        return False

    tier = row.get("tier")
    expected_pick = side if tier in {"A", "B", "C"} else None
    if row.get("pick") != expected_pick or row.get("value_side") != side:
        return False
    expected_lean = "yes" if expected_probability >= 0.5 else "no"
    if row.get("forecast_lean") != expected_lean:
        return False

    market_probability = row.get("market_probability")
    visible_edge = row.get("edge")
    if market_probability is None:
        if visible_edge is not None:
            return False
    else:
        market_number = _finite_number(market_probability)
        if (
            market_number is None
            or not 0.0 <= market_number <= 1.0
            or not _same_number(
                visible_edge,
                probability - market_number,
                tolerance=0.000101,
            )
        ):
            return False

    quote = _utc_timestamp(row.get("quote_fetched_at"))
    tier_quote = _utc_timestamp(row.get("tier_quote_fetched_at"))
    close = _utc_timestamp(row.get("close_time"))
    tier_close = _utc_timestamp(row.get("tier_close_time"))
    if (
        quote is None
        or tier_quote is None
        or quote != tier_quote
        or close is None
        or tier_close is None
        or close != tier_close
        or not _same_number(
            row.get("quote_age_seconds"),
            row.get("tier_quote_age_seconds"),
            tolerance=0.000001,
        )
    ):
        return False
    return True


def _public_tier_label(
    row: dict[str, Any],
    *,
    generated_at: datetime,
    current: datetime,
    require_display_model_provenance: bool = False,
) -> tuple[str, str]:
    """Validate a display tier against its row and the public read clock."""
    from autonomy.tier_policy import (
        MAX_QUOTE_AGE_SECONDS,
        MAX_QUOTE_FUTURE_SKEW_SECONDS,
        TIER_POLICY_VERSION,
        tier_snapshot_is_valid,
    )

    if row.get("tier_policy_version") == "unattributed":
        reason = str(row.get("tier_reason") or "unattributed_model_evidence")
        return "UNATTRIBUTED", reason
    if row.get("tier_policy_version") != TIER_POLICY_VERSION:
        return "UNATTRIBUTED", "legacy_or_superseded_tier_policy"
    if (
        row.get("tier_reason") == "no_executable_depth"
        and tier_snapshot_is_valid(
            row,
            ticker=str(row.get("ticker") or ""),
        )
    ):
        return "UNATTRIBUTED", "no_executable_depth"
    if not _visible_tier_snapshot_is_bound(row):
        return "UNATTRIBUTED", "snapshot_not_bound_to_visible_row"
    if require_display_model_provenance:
        # A display refresh may update the quote clock, but only a recent,
        # tamper-evident cycle forecast may supply the probability.  This is in
        # addition to (never instead of) the tier-policy hash and row bindings.
        from autonomy.sports_board_refresh import (
            validate_display_model_provenance,
        )

        model_valid, model_reason = validate_display_model_provenance(
            row,
            current=current,
        )
        if not model_valid:
            return "UNATTRIBUTED", model_reason
    assessed = _utc_timestamp(row.get("tier_assessed_at"))
    quoted = _utc_timestamp(row.get("tier_quote_fetched_at"))
    close = _utc_timestamp(row.get("tier_close_time"))
    if assessed is None or quoted is None or close is None:
        return "UNATTRIBUTED", "invalid_assessment_clock"
    if assessed > generated_at:
        return "UNATTRIBUTED", "assessment_after_board_generation"
    if assessed > current:
        return "UNATTRIBUTED", "assessment_after_read_time"
    if close <= generated_at or close <= current:
        return "UNATTRIBUTED", "market_expired_for_board"
    if (generated_at - assessed).total_seconds() > MAX_ASSESSMENT_TO_BOARD_SECONDS:
        return "UNATTRIBUTED", "assessment_too_old_for_board_generation"

    generation_quote_age = (generated_at - quoted).total_seconds()
    if generation_quote_age < -MAX_QUOTE_FUTURE_SKEW_SECONDS:
        return "UNATTRIBUTED", "quote_after_board_generation"
    if generation_quote_age > MAX_QUOTE_AGE_SECONDS:
        return "UNATTRIBUTED", "quote_stale_at_board_generation"

    read_quote_age = (current - quoted).total_seconds()
    if read_quote_age < -MAX_QUOTE_FUTURE_SKEW_SECONDS:
        return "UNATTRIBUTED", "quote_after_read_time"
    if read_quote_age > MAX_QUOTE_AGE_SECONDS:
        return "UNATTRIBUTED", "quote_stale_at_read_time"
    tier = row.get("tier")
    if tier in {"A", "B", "C"}:
        return str(tier), "validated_current_policy_snapshot"
    return "WATCH", "validated_current_policy_watch"


def _apply_public_tier_integrity(
    rows: list[dict[str, Any]],
    *,
    generated_at: datetime,
    current: datetime,
    require_display_model_provenance: bool = False,
) -> None:
    """Set server-derived buckets and reapply cross-row A scarcity caps."""
    for row in rows:
        label, reason = _public_tier_label(
            row,
            generated_at=generated_at,
            current=current,
            require_display_model_provenance=require_display_model_provenance,
        )
        row["tier_display_bucket"] = label
        row["tier_display_reason"] = reason
        row["tier_display_scarcity_demoted"] = False

    _enforce_public_a_scarcity(rows)


def _enforce_public_a_scarcity(rows: list[dict[str, Any]]) -> None:
    """Reapply A scarcity to already validated public display buckets."""
    from autonomy.tier_policy import A_MAX_PER_EVENT, A_MAX_PER_SCOPE

    a_rows = sorted(
        (row for row in rows if row["tier_display_bucket"] == "A"),
        key=lambda row: (
            -float(row["tier_after_fee_edge"]),
            float(row["tier_uncertainty"]),
            str(row.get("ticker") or ""),
        ),
    )
    event_counts: dict[str, int] = {}
    scope_counts: dict[str, int] = {}
    for row in a_rows:
        event = str(row.get("tier_event_key") or "")
        scope = str(row.get("tier_scope") or "")
        if (
            event_counts.get(event, 0) >= A_MAX_PER_EVENT
            or scope_counts.get(scope, 0) >= A_MAX_PER_SCOPE
        ):
            # A base candidate necessarily clears B's numerical hurdle.  The
            # signed snapshot is retained for audit, while the public bucket
            # reflects the cycle-wide scarcity rule the forged artifact
            # omitted.
            row["tier_display_bucket"] = "B"
            row["tier_display_reason"] = "a_scarcity_cap_enforced_at_read"
            row["tier_display_scarcity_demoted"] = True
            continue
        event_counts[event] = event_counts.get(event, 0) + 1
        scope_counts[scope] = scope_counts.get(scope, 0) + 1


def _force_public_unattributed(
    row: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    """Copy a row as context while removing every current tier claim."""
    copied = dict(row)
    previous_tier = (
        copied.get("tier")
        if copied.get("tier") is not None
        else copied.get("last_issued_tier")
    )
    previous_assessed = (
        copied.get("tier_assessed_at")
        or copied.get("last_issued_tier_assessed_at")
    )
    previous_reason = (
        copied.get("tier_reason")
        if copied.get("tier") is not None
        else copied.get("last_issued_tier_reason")
    )
    for key in tuple(copied):
        if key == "tier" or key.startswith("tier_"):
            copied.pop(key, None)
    copied.update({
        "tier": None,
        "tier_policy_version": "unattributed",
        "tier_reason": reason,
        "tier_display_bucket": "UNATTRIBUTED",
        "tier_display_reason": reason,
        "pick": None,
        "value_side": None,
        "entry_price_cents": None,
        "modeled_fee_cents": None,
        "gross_executable_edge": None,
        "after_fee_edge": None,
        "last_issued_tier": previous_tier,
        "last_issued_tier_assessed_at": previous_assessed,
        "last_issued_tier_reason": previous_reason,
        "last_issued_tier_status": "EXPIRED_RESEARCH_CONTEXT_ONLY",
    })
    return copied


def _display_label(row: dict[str, Any]) -> str:
    label = row.get("tier_display_bucket")
    return str(label) if label in _TIER_LABELS else _tier_label(row)


def _tier_label(row: dict[str, Any]) -> str:
    """Return the honest display bucket for a board row.

    A row is WATCH only when it was actually assessed by the current policy
    and missed its letter-tier hurdle. Legacy/missing/mismatched policy rows
    are evidence-free for the current policy and remain UNATTRIBUTED.
    """
    from autonomy.tier_policy import tier_snapshot_is_valid

    if not tier_snapshot_is_valid(
        row, ticker=str(row.get("ticker") or "")
    ):
        return "UNATTRIBUTED"
    tier = row.get("tier")
    return str(tier) if tier in {"A", "B", "C"} else "WATCH"


def current_board_tier_distribution(board: dict[str, Any] | None) -> dict[str, Any]:
    """Summarize the complete artifact board without consulting the ledger."""
    counts = {label: 0 for label in _TIER_LABELS}
    if not isinstance(board, dict):
        return {"n": 0, "counts": counts, "percentages": dict(counts), "by_scope": {}}

    flat: list[dict[str, Any]] = []
    by_scope: dict[str, dict[str, int]] = {}
    for scope, markets in (board.get("groups") or {}).items():
        scope_counts = {label: 0 for label in _TIER_LABELS}
        for rows in (markets or {}).values():
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                flat.append(row)
                scope_counts[_display_label(row)] += 1
        by_scope[str(scope)] = scope_counts

    # Tiny/synthetic artifacts may carry only ``top``. Never treat a truncated
    # top list as the complete distribution.
    if (
        not flat
        and isinstance(board.get("top"), list)
        and int(board.get("rows") or 0) <= len(board["top"])
    ):
        flat = [row for row in board["top"] if isinstance(row, dict)]
        for row in flat:
            scope = str(row.get("league") or "OTHER")
            scope_counts = by_scope.setdefault(
                scope, {label: 0 for label in _TIER_LABELS}
            )
            scope_counts[_display_label(row)] += 1

    for row in flat:
        counts[_display_label(row)] += 1
    total = len(flat)
    return {
        "n": total,
        "counts": counts,
        "percentages": {
            label: round(count / total, 4) if total else 0.0
            for label, count in counts.items()
        },
        "by_scope": by_scope,
        "policy_versions": sorted({
            str(row.get("tier_policy_version"))
            for row in flat
            if row.get("tier_policy_version")
        }),
    }

def _group_of(ticker: str) -> tuple[str, str]:
    """(league, bet type) for grouping; non-sports fall to their subject."""
    spec = spec_for(ticker)
    if spec is not None:
        label = spec.market_type
        if spec.segment != FULL:
            label = f"{spec.segment}_{spec.market_type}"
        if spec.is_prop and spec.stat:
            label = f"prop_{spec.stat}"
        return spec.league, label
    subject = prediction_subject(ticker)
    return subject or "other", "market"


def _matchup(ticker: str) -> str:
    """Human-readable matchup (``SD vs ATL``), ticker-only, fail-soft to raw."""
    from autonomy.market_labels import humanize_ticker

    return humanize_ticker(ticker)["matchup"]


def _rank_key(row: dict[str, Any]) -> tuple[float, float, float, str]:
    tier_rank = {"A": 3.0, "B": 2.0, "C": 1.0}.get(
        _display_label(row), 0.0
    )
    executable = row.get("after_fee_edge")
    raw_edge = row.get("edge")
    value_rank = (
        float(executable)
        if tier_rank > 0.0 and isinstance(executable, (int, float))
        else abs(float(raw_edge))
        if isinstance(raw_edge, (int, float))
        else -1.0
    )
    uncertainty = row.get("uncertainty")
    return (
        tier_rank,
        value_rank,
        -float(uncertainty) if isinstance(uncertainty, (int, float)) else -1.0,
        str(row.get("ticker") or ""),
    )


def _row_series_tags(row: dict[str, Any]) -> Any:
    """Return denial-only venue tag evidence retained on a board row."""
    return row.get("series_tags") or row.get("tags")


def _finish_board(board_rows: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    """Rank, group, and wrap raw board rows into the served payload."""
    excluded_data_only_rows = sum(
        1
        for row in board_rows
        if is_data_only_target(
            str(row.get("ticker") or ""),
            category=row.get("category"),
            vertical=row.get("vertical"),
        )
    )
    excluded_equity_index_rows = sum(
        1
        for row in board_rows
        if is_equity_index_target(
            str(row.get("ticker") or ""),
            category=row.get("category"),
            vertical=row.get("vertical"),
            series_tags=_row_series_tags(row),
        )
    )
    board_rows = [
        row for row in board_rows
        if not is_prediction_quarantined_target(
            str(row.get("ticker") or ""),
            category=row.get("category"),
            vertical=row.get("vertical"),
            series_tags=_row_series_tags(row),
        )
    ]
    for row in board_rows:
        row["tier_display_bucket"] = _tier_label(row)

    board_rows.sort(key=_rank_key, reverse=True)
    for position, row in enumerate(board_rows, start=1):
        row["rank"] = position
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in board_rows:
        groups.setdefault(row["league"], {}).setdefault(row["bet_type"], []).append(row)
    tier_counts = {label: 0 for label in _TIER_LABELS}
    for row in board_rows:
        tier_counts[_display_label(row)] += 1
    total = len(board_rows)
    return {
        **_sports_roster_fields(),
        "rows": total,
        "top": board_rows[:25],
        "groups": groups,
        "excluded_data_only_rows": excluded_data_only_rows,
        "excluded_equity_index_rows": excluded_equity_index_rows,
        "tier_distribution": {
            "counts": tier_counts,
            "percentages": {
                label: round(count / total, 4) if total else 0.0
                for label, count in tier_counts.items()
            },
        },
        "note": (
            "Display-only ranking of every market the brain currently prices. "
            "A/B/C require fee-adjusted executable quote value plus uncertainty gates; "
            "WATCH means a current-policy quote did not clear a letter-tier hurdle; "
            "UNATTRIBUTED means no valid current-policy assessment exists."),
        **extra,
    }


def write_board_artifact(
    scored: list[tuple[Any, Any]],
    *,
    path: Path | None = None,
    now_iso: str | None = None,
    tier_assignments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write the board from the cycle's in-memory (market, forecast) pairs.

    Called by the brain at the end of every cycle -- titles included, no DB
    touched, atomic replace so the dashboard never reads a torn file."""
    from datetime import datetime, timezone

    from autonomy.market_labels import humanize_market
    from autonomy.tier_policy import assign_cycle_tiers, normalized_quote_sizes

    assignments = (
        tier_assignments if tier_assignments is not None else assign_cycle_tiers(scored)
    )

    board_rows: list[dict[str, Any]] = []
    for market, forecast in scored:
        probability = float(forecast.probability_yes)
        market_prob = forecast.market_implied_yes
        league, bet_type = _group_of(market.ticker)
        title = getattr(market, "title", None)
        hl = humanize_market(market.ticker, title)
        assessment = assignments[market.ticker]
        tier_features = assessment.feature_fields()
        quote_sizes = normalized_quote_sizes(market)
        raw_market = getattr(market, "raw", None)
        raw_market = raw_market if isinstance(raw_market, dict) else {}
        vertical = getattr(market, "vertical", None)
        vertical = getattr(vertical, "value", vertical)
        row = {
            "ticker": market.ticker,
            "category": raw_market.get("category") or getattr(market, "category", None),
            "series_tags": raw_market.get("series_tags") or raw_market.get("tags"),
            "vertical": vertical,
            "title": title or hl["label"],
            "matchup": hl["matchup"],
            "market": hl["market"],
            "subject": hl["subject"],
            "subject_team": hl["subject_team"],
            "label": hl["label"],
            "game_date": hl["date"],
            "event_date": hl["event_date"],
            "event_id": hl["event_id"],
            "league": league,
            "bet_type": bet_type,
            "probability": round(probability, 4),
            "market_probability": (
                round(float(market_prob), 4)
                if isinstance(market_prob, (int, float)) else None),
            "edge": (round(probability - float(market_prob), 4)
                     if isinstance(market_prob, (int, float)) else None),
            # ``pick`` is the quoted value side, not the most-likely outcome.
            # The latter is exposed separately as forecast_lean.
            "pick": assessment.side if assessment.tier else None,
            "value_side": assessment.side,
            "forecast_lean": "yes" if probability >= 0.5 else "no",
            "tier": assessment.tier,
            "tier_base": assessment.base_tier,
            "tier_policy_version": assessment.policy_version,
            "tier_policy_sha256": tier_features.get("tier_policy_sha256"),
            "tier_snapshot_sha256": tier_features.get("tier_snapshot_sha256"),
            "tier_score": (
                round(float(assessment.score), 6)
                if assessment.score is not None else None
            ),
            "tier_reason": assessment.reason,
            "tier_scarcity_demoted": assessment.scarcity_demoted,
            "entry_price_cents": assessment.entry_price_cents,
            "modeled_fee_cents": assessment.modeled_fee_cents,
            "gross_executable_edge": (
                round(float(assessment.gross_executable_edge), 6)
                if assessment.gross_executable_edge is not None else None
            ),
            "after_fee_edge": (
                round(float(assessment.after_fee_edge), 6)
                if assessment.after_fee_edge is not None else None
            ),
            "selected_bid_size_fp": assessment.selected_bid_size_fp,
            "selected_ask_size_fp": assessment.selected_ask_size_fp,
            "effective_depth": assessment.effective_depth,
            "depth_source": assessment.depth_source,
            "tier_assessed_at": assessment.assessed_at,
            "quote_fetched_at": assessment.quote_fetched_at,
            "quote_age_seconds": assessment.quote_age_seconds,
            "uncertainty": round(float(forecast.uncertainty), 3),
            # Wave-26: the cycle's live book, captured point-in-time so the
            # vNext shadow runtime issues episodes from this artifact with
            # zero additional network reads.
            "yes_bid": getattr(market, "yes_bid", None),
            "yes_ask": getattr(market, "yes_ask", None),
            "no_bid": getattr(market, "no_bid", None),
            "no_ask": getattr(market, "no_ask", None),
            "liquidity": getattr(market, "liquidity", None),
            **quote_sizes,
            "close_time": getattr(market, "close_time", None),
        }
        row.update(tier_features)
        row["tier_display_bucket"] = _tier_label(row)
        board_rows.append(row)
    payload = _finish_board(
        board_rows,
        generated_at=now_iso or datetime.now(timezone.utc).isoformat(),
        source="cycle_artifact",
    )
    target = path or BOARD_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    temporary.replace(target)
    return payload


def read_board_artifact(
    path: Path | None = None,
    *,
    now: Any | None = None,
) -> dict[str, Any]:
    """Read the board JSON without ever opening ``ledger.db``.

    A stale artifact is still returned intact and explicitly labelled so the
    UI can remain available without misrepresenting its freshness. Missing or
    invalid artifacts produce a structured unavailable payload rather than a
    silent ledger fallback.
    """
    target = path or BOARD_PATH
    roster_fields = _sports_roster_fields()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            **roster_fields,
            "artifact_status": "MISSING",
            "error": "The cycle board artifact is missing.",
            "generated_at": None,
            "age_seconds": None,
            "stale": True,
            "rows": 0,
            "groups": {},
            "top": [],
        }
    except OSError as exc:
        return {
            **roster_fields,
            "artifact_status": "UNREADABLE",
            "error": f"The cycle board artifact cannot be read: {type(exc).__name__}.",
            "generated_at": None,
            "age_seconds": None,
            "stale": True,
            "rows": 0,
            "groups": {},
            "top": [],
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            **roster_fields,
            "artifact_status": "INVALID",
            "error": "The cycle board artifact is not valid JSON.",
            "generated_at": None,
            "age_seconds": None,
            "stale": True,
            "rows": 0,
            "groups": {},
            "top": [],
        }

    try:
        if not isinstance(payload, dict):
            raise TypeError("board payload must be an object")
        stamp = _utc_timestamp(payload.get("generated_at"))
        if stamp is None:
            raise ValueError("generated_at is not timezone-aware")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("current timestamp is not timezone-aware")
        current = current.astimezone(timezone.utc)
        age = (current - stamp).total_seconds()
        if age < -ARTIFACT_FUTURE_SKEW_SECONDS:
            raise ValueError("generated_at is excessively future-dated")
        age = max(0.0, age)
    except (AttributeError, TypeError, ValueError):
        return {
            **roster_fields,
            "artifact_status": "INVALID",
            "error": "The cycle board artifact has no valid generated_at timestamp.",
            "generated_at": payload.get("generated_at") if isinstance(payload, dict) else None,
            "age_seconds": None,
            "stale": True,
            "rows": 0,
            "groups": {},
            "top": [],
        }

    groups = payload.get("groups")
    top = payload.get("top")
    rows_claimed = payload.get("rows")
    if (
        not isinstance(groups, dict)
        or not isinstance(top, list)
        or not isinstance(rows_claimed, int)
        or rows_claimed < 0
    ):
        return {
            **roster_fields,
            "artifact_status": "INVALID",
            "error": "The cycle board artifact has an invalid board schema.",
            "generated_at": payload.get("generated_at"),
            "age_seconds": round(age, 1),
            "stale": True,
            "rows": 0,
            "groups": {},
            "top": [],
        }
    group_rows: list[dict[str, Any]] = []
    try:
        for scope, markets in groups.items():
            if not isinstance(markets, dict):
                raise TypeError
            for market_type, rows in markets.items():
                if not isinstance(rows, list) or not all(
                    isinstance(row, dict) for row in rows
                ):
                    raise TypeError
                if any(
                    str(row.get("league") or "") != str(scope)
                    or str(row.get("bet_type") or "") != str(market_type)
                    for row in rows
                ):
                    raise TypeError
                group_rows.extend(rows)
        if rows_claimed != len(group_rows) or not all(
            isinstance(row, dict) for row in top
        ):
            raise TypeError
    except TypeError:
        return {
            **roster_fields,
            "artifact_status": "INVALID",
            "error": "The cycle board artifact row count/schema is inconsistent.",
            "generated_at": payload.get("generated_at"),
            "age_seconds": round(age, 1),
            "stale": True,
            "rows": 0,
            "groups": {},
            "top": [],
        }
    # Re-enforce the target boundary at the public read edge.  The writer also
    # excludes these rows, but a legacy, copied, or locally modified artifact
    # must never restore quarantined targets to the betting guide.
    excluded_data_only_rows = sum(
        1
        for row in group_rows
        if is_data_only_target(
            str(row.get("ticker") or ""),
            category=row.get("category"),
            vertical=row.get("vertical"),
        )
    )
    excluded_equity_index_rows = sum(
        1
        for row in group_rows
        if is_equity_index_target(
            str(row.get("ticker") or ""),
            category=row.get("category"),
            vertical=row.get("vertical"),
            series_tags=_row_series_tags(row),
        )
    )
    eligible_rows = [
        row
        for row in group_rows
        if not is_prediction_quarantined_target(
            str(row.get("ticker") or ""),
            category=row.get("category"),
            vertical=row.get("vertical"),
            series_tags=_row_series_tags(row),
        )
    ]
    rebuilt_groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in eligible_rows:
        rebuilt_groups.setdefault(str(row.get("league") or ""), {}).setdefault(
            str(row.get("bet_type") or ""), []
        ).append(row)
    groups = rebuilt_groups
    payload["groups"] = groups
    payload["rows"] = len(eligible_rows)
    payload["excluded_data_only_rows"] = excluded_data_only_rows
    payload["excluded_equity_index_rows"] = excluded_equity_index_rows

    _apply_public_tier_integrity(
        eligible_rows,
        generated_at=stamp,
        current=current,
        require_display_model_provenance=(
            payload.get("source") == "sports_display_refresh_v1"
        ),
    )
    ranked_rows = sorted(eligible_rows, key=_rank_key, reverse=True)
    for position, row in enumerate(ranked_rows, start=1):
        row["rank"] = position
    for markets in groups.values():
        for rows in markets.values():
            rows.sort(key=lambda row: int(row["rank"]))
    # ``top`` is never a second source of truth.  Derive it from the validated
    # complete groups so copied, omitted, reordered, or forged top rows cannot
    # diverge from the board operators inspect.
    payload["top"] = ranked_rows[:25]
    distribution = current_board_tier_distribution(payload)
    payload["tier_distribution"] = {
        "counts": distribution["counts"],
        "percentages": distribution["percentages"],
    }
    # The roster is server-authored capability metadata, not trusted from the
    # artifact and not derived from whichever leagues happen to have rows.
    payload.update(roster_fields)

    stale = age > ARTIFACT_FRESH_SECONDS
    payload["artifact_status"] = "STALE" if stale else "FRESH"
    payload["age_seconds"] = round(age, 1)
    payload["stale"] = stale
    return payload


def read_current_board_artifact(
    base_path: Path | None = None,
    *,
    display_path: Path | None = None,
    now: Any | None = None,
) -> dict[str, Any]:
    """Read the newest valid public board from files only.

    ``bet_board.json`` remains the cycle/execution artifact.  The bounded
    sports refresher writes ``bet_board_display.json`` instead, and dashboard
    callers use this selector.  Selection is per sports series and performs no
    network or ledger work: unrelated work in a newer broad cycle cannot hide
    a fresher sports overlay, while a truly newer quote for one series can win
    without replacing the other refreshed series.
    """
    base_target = base_path or BOARD_PATH
    if display_path is None:
        display_target = Path(base_target).with_name(DISPLAY_BOARD_PATH.name)
    else:
        display_target = display_path
    base = read_board_artifact(base_target, now=now)
    display = read_board_artifact(display_target, now=now)

    available_statuses = {"FRESH", "STALE"}
    base_stamp = _utc_timestamp(base.get("generated_at"))
    display_stamp = _utc_timestamp(display.get("generated_at"))
    display_available = (
        display.get("artifact_status") in available_statuses
        and display_stamp is not None
    )
    base_available = (
        base.get("artifact_status") in available_statuses
        and base_stamp is not None
    )
    if not display_available:
        base["selected_artifact"] = "cycle"
        base["display_artifact_status"] = display.get("artifact_status")
        base["display_artifact_generated_at"] = display.get("generated_at")
        return base

    def _rows(board: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            row
            for markets in (board.get("groups") or {}).values()
            if isinstance(markets, dict)
            for group_rows in markets.values()
            if isinstance(group_rows, list)
            for row in group_rows
            if isinstance(row, dict)
        ]

    raw_display_rows = _rows(display)
    base_rows = _rows(base) if base_available else []
    coverage_date = str(display.get("coverage_date") or "")
    covered_series = {
        str(value).upper() for value in (display.get("covered_series") or [])
        if value
    }
    requested_series = {
        str(value).upper() for value in (display.get("requested_series") or [])
        if value
    }
    if not covered_series:
        covered_series = {
            str(value).upper()
            for value in (display.get("observed_series") or [])
            if value
        }
    requested_series.update(covered_series)
    series_refreshed_raw = display.get("series_refreshed_at")
    series_refreshed = (
        series_refreshed_raw if isinstance(series_refreshed_raw, dict) else {}
    )
    # Normalize a legacy/premerged display artifact to the overlay contract at
    # read time.  Only its declared current-day sports series can participate.
    display_rows = [
        row for row in raw_display_rows
        if (
            str(row.get("event_date") or "") == coverage_date
            and series_of(str(row.get("ticker") or "")) in requested_series
        )
    ]

    def _clock(row: dict[str, Any]) -> datetime:
        return (
            _utc_timestamp(row.get("tier_quote_fetched_at"))
            or _utc_timestamp(row.get("quote_fetched_at"))
            or datetime.min.replace(tzinfo=timezone.utc)
        )

    base_current: dict[str, list[dict[str, Any]]] = {}
    display_current: dict[str, list[dict[str, Any]]] = {}
    carried: list[dict[str, Any]] = []
    for row in base_rows:
        series = series_of(str(row.get("ticker") or ""))
        if (
            str(row.get("event_date") or "") == coverage_date
            and series in requested_series
        ):
            base_current.setdefault(series, []).append(row)
        else:
            carried.append(row)
    for row in display_rows:
        display_current.setdefault(
            series_of(str(row.get("ticker") or "")), []
        ).append(row)

    selected_overlay: list[dict[str, Any]] = []
    for series in sorted(requested_series):
        base_series = base_current.get(series, [])
        display_series = display_current.get(series, [])
        if series not in covered_series:
            # A failed series has no current quote authority.  Retain the most
            # recent known roster only as neutral context, regardless of
            # whether it came from the cycle or a prior normalized overlay.
            failed_by_ticker: dict[str, dict[str, Any]] = {}
            for row in base_series + display_series:
                ticker = str(row.get("ticker") or "")
                held = failed_by_ticker.get(ticker)
                if held is None or _clock(row) > _clock(held):
                    failed_by_ticker[ticker] = row
            selected_overlay.extend(
                _force_public_unattributed(
                    row,
                    reason="series_refresh_failed_or_unknown",
                )
                for row in failed_by_ticker.values()
            )
            continue
        base_clock = max((_clock(row) for row in base_series), default=None)
        series_page_clock = (
            _utc_timestamp(series_refreshed.get(series))
        )
        display_clock = max(
            (
                *(_clock(row) for row in display_series),
                *(() if series_page_clock is None else (series_page_clock,)),
            ),
            default=None,
        )
        # Select at series granularity so a complete newer listing roster does
        # not retain contracts that disappeared from the venue.  Overall board
        # generated_at is deliberately irrelevant here.
        if (
            base_clock is not None
            and (display_clock is None or base_clock > display_clock)
        ):
            chosen = base_series
        else:
            chosen = display_series
        # Defensive ticker-level de-duplication within the selected series.
        by_ticker: dict[str, dict[str, Any]] = {}
        for row in chosen:
            ticker = str(row.get("ticker") or "")
            held = by_ticker.get(ticker)
            if held is None or _clock(row) > _clock(held):
                by_ticker[ticker] = row
        selected_overlay.extend(by_ticker.values())

    combined = carried + selected_overlay
    deduped: dict[str, dict[str, Any]] = {}
    for row in combined:
        ticker = str(row.get("ticker") or "")
        held = deduped.get(ticker)
        if held is None or _clock(row) > _clock(held):
            deduped[ticker] = row
    combined = list(deduped.values())
    _enforce_public_a_scarcity(combined)
    combined.sort(key=_rank_key, reverse=True)
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for position, row in enumerate(combined, start=1):
        row["rank"] = position
        groups.setdefault(str(row.get("league") or ""), {}).setdefault(
            str(row.get("bet_type") or ""), []
        ).append(row)

    selected = dict(display)
    selected.update({
        "source": "composite_public_board_v1",
        "selected_artifact": "sports_display_overlay",
        "groups": groups,
        "rows": len(combined),
        "top": combined[:25],
        "cycle_artifact_status": base.get("artifact_status"),
        "cycle_artifact_generated_at": base.get("generated_at"),
        "display_artifact_status": display.get("artifact_status"),
        "display_artifact_generated_at": display.get("generated_at"),
        "overlay_contract_version": 1,
        "overlay_only": True,
        "overlay_format_normalized": not bool(display.get("overlay_only")),
        **_sports_roster_fields(),
    })
    distribution = current_board_tier_distribution(selected)
    selected["tier_distribution"] = {
        "counts": distribution["counts"],
        "percentages": distribution["percentages"],
    }
    return selected


def _artifact_board(path: Path) -> dict[str, Any] | None:
    """Fresh-only compatibility wrapper for the non-request fallback helper."""
    payload = read_board_artifact(path)
    return payload if payload.get("artifact_status") == "FRESH" else None


def assemble_bet_board(
    db_path: str = "runtime/autonomy/ledger.db",
    *,
    fresh_hours: float = FRESH_HOURS,
    conn: sqlite3.Connection | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """The board payload: cycle artifact first, ledger fallback (cold start)."""
    if conn is None:
        artifact = _artifact_board(artifact_path or BOARD_PATH)
        if artifact is not None:
            return artifact
    owns = conn is None
    if conn is None:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
        except sqlite3.Error as exc:
            return {
                **_sports_roster_fields(),
                "error": f"{type(exc).__name__}: {exc}",
                "rows": 0,
                "groups": {},
            }
    try:
        try:
            from autonomy.retention import install_signal_history

            install_signal_history(conn)
            rows = conn.execute(
                """
                SELECT s.market_ticker, s.probability_yes, s.uncertainty,
                       s.created_at, s.features
                FROM signal_history s
                WHERE s.source = ?
                  AND s.created_at >= datetime('now', ?)
                  AND s.market_ticker NOT IN (SELECT market_ticker FROM settlements)
                """,
                (FUSED_SOURCE, f"-{float(fresh_hours)} hours"),
            ).fetchall()
        except sqlite3.Error as exc:
            return {
                **_sports_roster_fields(),
                "error": f"{type(exc).__name__}: {exc}",
                "rows": 0,
                "groups": {},
            }
    finally:
        if owns:
            conn.close()

    latest: dict[str, tuple[str, float, float, dict[str, Any]]] = {}
    for ticker, probability, uncertainty, created_at, features_raw in rows:
        ticker = str(ticker)
        held = latest.get(ticker)
        if held is not None and str(created_at) <= held[0]:
            continue
        try:
            features = json.loads(features_raw) if isinstance(features_raw, str) else (features_raw or {})
        except (TypeError, ValueError):
            features = {}
        latest[ticker] = (str(created_at), float(probability), float(uncertainty), features)

    from autonomy.market_labels import humanize_market
    from autonomy.tier_policy import assessment_from_features

    board_rows: list[dict[str, Any]] = []
    for ticker, (created_at, probability, uncertainty, features) in latest.items():
        market_prob = features.get("market_implied_yes")
        edge = None
        if isinstance(market_prob, (int, float)):
            edge = probability - float(market_prob)
        league, bet_type = _group_of(ticker)
        hl = humanize_market(ticker)
        assessment = assessment_from_features(ticker, features)
        row = {
            "ticker": ticker,
            "category": features.get("market_category") or features.get("category"),
            "series_tags": features.get("series_tags") or features.get("tags"),
            "vertical": features.get("vertical"),
            "matchup": hl["matchup"],
            "market": hl["market"],
            "subject": hl["subject"],
            "subject_team": hl["subject_team"],
            "label": hl["label"],
            "game_date": hl["date"],
            "event_date": hl["event_date"],
            "event_id": hl["event_id"],
            "league": league,
            "bet_type": bet_type,
            "probability": round(probability, 4),
            "market_probability": (
                round(float(market_prob), 4)
                if isinstance(market_prob, (int, float)) else None),
            "edge": round(edge, 4) if edge is not None else None,
            "pick": assessment.side if assessment.tier else None,
            "value_side": assessment.side,
            "forecast_lean": "yes" if probability >= 0.5 else "no",
            "tier": assessment.tier,
            "tier_base": assessment.base_tier,
            "tier_policy_version": assessment.policy_version,
            "tier_policy_sha256": features.get("tier_policy_sha256"),
            "tier_snapshot_sha256": features.get("tier_snapshot_sha256"),
            "tier_score": assessment.score,
            "tier_reason": assessment.reason,
            "tier_scarcity_demoted": assessment.scarcity_demoted,
            "entry_price_cents": assessment.entry_price_cents,
            "modeled_fee_cents": assessment.modeled_fee_cents,
            "gross_executable_edge": assessment.gross_executable_edge,
            "after_fee_edge": assessment.after_fee_edge,
            "tier_assessed_at": assessment.assessed_at,
            "quote_fetched_at": assessment.quote_fetched_at,
            "quote_age_seconds": assessment.quote_age_seconds,
            "uncertainty": round(uncertainty, 3),
            "as_of": created_at,
        }
        row.update({
            key: value
            for key, value in features.items()
            if key == "tier" or key.startswith("tier_")
        })
        row["tier_display_bucket"] = _tier_label(row)
        board_rows.append(row)

    return _finish_board(
        board_rows,
        generated_at=max((row["as_of"] for row in board_rows), default=None),
        fresh_hours=fresh_hours,
        source="ledger_fallback",
    )
