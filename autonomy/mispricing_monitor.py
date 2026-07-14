"""Mispricing sweep: one buy-low/opportunist pass over a batch of markets.

Ties the pieces together into a single, testable pass — the body of the
dedicated fast monitor loop (P2b):

  scan -> our fused forecast (model_prob) -> de-vigged book (book_prob, sports)
       -> triangulated MispricingAssessment -> OpportunistEngine (patience)
       -> a JSON-able report the dashboard renders.

Pure and injectable: the caller supplies the market list, a ``forecast_fn``
(our model's probability for a market; None -> skip, fail-closed), an optional
``book_fn`` (de-vigged sportsbook probability), and an optional stateful
``OpportunistEngine`` carried across passes. ``run_mispricing_sweep`` itself
still does no I/O — the runner script does the scanning and scheduling, and
calls the ``persist_book_tape`` / ``persist_paper_entries`` helpers below
(WS-8) to write the two new evidence artifacts this module now also owns.

Everything downstream is challenger / paper evidence — the sweep never places
an order; it surfaces the shortlist and the opportunist strikes for review.

WS-8 (spec §3.2, CLV grading): every pass also emits ``tape_rows`` (one
``{ticker, ts, book_prob, kalshi_mid, close_time}`` row per assessed market)
and ``entries`` (one row per shortlist/opportunist item, tagged with a
best-effort ``source``/``market_type`` for grading). These feed
``autonomy/clv.py`` and ``scripts/run_dummy_clv_grader.py`` — CLV is
evidence for review, never a promotion gate.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from autonomy.coherence import (
    TIER_CROSS_CONFIRMED,
    TIER_RANK,
    TIER_STRUCTURAL,
    build_game_lattices,
    cross_family_incoherence,
    ladder_violations,
    lattice_conviction,
)
from autonomy.mispricing import (
    DEFAULT_AGREE_MARGIN,
    DEFAULT_EDGE_THRESHOLD,
    MispricingAssessment,
    MispricingMonitor,
)
from autonomy.opportunist import OpportunistEngine, Opportunity
from autonomy.taxonomy import market_type_for

# Report caps: at most this many per-game lattice rows, richest tier first.
MAX_LATTICES = 20

# WS-8: ticker series tokens that reveal a sports market's family without
# needing the features/source a ledger signal would carry. Paper entries
# here come from a fused or live specialist forecast, not one named signal,
# so they have no ``features["market_type"]`` stamp; the Kalshi series
# fragment already encodes it (KXMLBSPREAD -> spread, KXMLBGAME -> winner,
# ...). Crypto tickers fall through to ``autonomy.taxonomy.market_type_for``,
# which parses the contract family from the ticker directly.
_SPORTS_MARKET_TYPE_TOKENS: tuple[tuple[str, str], ...] = (
    ("SPREAD", "spread"),
    ("TOTAL", "total"),
    ("RFI", "yrfi"),
    ("GAME", "winner"),
)


def _entry_market_type(ticker: str) -> str:
    """Best-effort market_type for a monitor-sourced (feature-less) entry."""
    upper = str(ticker or "").upper()
    for token, market_type in _SPORTS_MARKET_TYPE_TOKENS:
        if token in upper:
            return market_type
    return market_type_for("", ticker, {})


def _assessment_row(a: MispricingAssessment) -> dict[str, Any]:
    return {
        "ticker": a.market_ticker,
        "side": a.side,
        "model_prob": round(a.model_prob, 4),
        "market_prob": None if a.market_prob is None else round(a.market_prob, 4),
        "book_prob": None if a.book_prob is None else round(a.book_prob, 4),
        "edge": round(a.edge, 4),
        "agreement": a.agreement,
        "confidence": a.confidence,
        "rationale": a.rationale,
        "conviction_tier": a.conviction_tier,
        "power_divergence": a.power_divergence,
        "ejection_events": list(a.ejection_events),
    }


def _lattice_section(
    markets: list[Any], assessments_by_ticker: dict[str, MispricingAssessment],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Build ALL per-game lattice rows (uncapped) + a ticker -> tier map.

    Fail-closed by construction: ``build_game_lattices`` only produces a
    ``GameLattice`` for games with at least one real cell (grouped through
    the real ``parse_sports_contract``, no hand-built dicts); a market that
    never parses to a sports contract simply never appears here, so a pass
    with no sports markets yields empty lattices/counts and an unchanged
    opportunist tier map -- byte-identical to pre-WS-5 behavior.

    Returns the FULL sorted row list (richest tier first) -- the caller caps
    the report's ``lattices`` display list at ``MAX_LATTICES``, but the
    ``structural_count``/``cross_confirmed_count`` totals must reflect every
    game that reached that tier, not just the ones that made the display cap.
    """
    lattices = build_game_lattices(markets, assessments_by_ticker)
    rows: list[dict[str, Any]] = []
    tier_by_ticker: dict[str, str] = {}
    for lattice in lattices:
        ladder_rows = [
            {**violation, "game_key": lattice.game_key}
            for family in ("spread", "total")
            for violation in ladder_violations(lattice.cells, family)
        ]
        incoherence_rows = cross_family_incoherence(lattice)
        conviction = lattice_conviction(lattice, assessments_by_ticker)
        tier = conviction["conviction_tier"]
        if tier in (TIER_STRUCTURAL, TIER_CROSS_CONFIRMED):
            for cell in lattice.cells:
                tier_by_ticker[cell.ticker] = tier
        rows.append({
            "game_key": lattice.game_key,
            "sport": lattice.sport,
            "conviction_tier": tier,
            "cell_count": len(lattice.cells),
            "ladder_violations": ladder_rows,
            "cross_family_incoherence": incoherence_rows,
        })

    rows.sort(key=lambda row: (TIER_RANK.get(row["conviction_tier"], 0), row["game_key"]), reverse=True)
    return rows, tier_by_ticker


def _tape_row(market: Any, assessment: MispricingAssessment, ts: str) -> dict[str, Any]:
    """One WS-8 book-tape row: {ticker, ts, book_prob, kalshi_mid, close_time}."""
    return {
        "ticker": assessment.market_ticker,
        "ts": ts,
        "book_prob": None if assessment.book_prob is None else round(assessment.book_prob, 4),
        "kalshi_mid": None if assessment.market_prob is None else round(assessment.market_prob, 4),
        "close_time": getattr(market, "close_time", None),
    }


def _entry_row(
    ticker: str, side: str, entry_kalshi_prob: float | None, source: str | None, ts: str,
) -> dict[str, Any] | None:
    """One WS-8 paper entry; None when there is nothing gradeable to persist."""
    if side not in ("YES", "NO") or entry_kalshi_prob is None:
        return None
    return {
        "ticker": ticker,
        "side": side,
        "entry_kalshi_prob": round(float(entry_kalshi_prob), 4),
        "source": source or "unknown",
        "market_type": _entry_market_type(ticker),
        "ts": ts,
    }


def _opportunity_row(o: Opportunity) -> dict[str, Any]:
    return {
        "ticker": o.ticker,
        "side": o.side,
        "conviction": round(o.conviction, 4),
        "anchor_prob": round(o.anchor_prob, 4),
        "entry_prob": round(o.entry_prob, 4),
        "edge": round(o.edge, 4),
        "deviation": round(o.deviation, 4),
        "confidence": o.confidence,
        "rationale": o.rationale,
        "power_divergence": o.power_divergence,
        "ejection_events": list(o.ejection_events),
    }


def _point_in_time_ejections(value: Any, received_at: str) -> tuple[dict[str, Any], ...]:
    """Normalize raw ejection dicts and stamp the local receipt time.

    The callback is an external-data boundary: malformed rows are quarantined
    by omission, and callback-provided receipt/proof flags cannot override the
    monitor's own observation time. These remain tier-1 raw observations.
    """
    if not isinstance(value, (list, tuple)):
        return ()
    rows: list[dict[str, Any]] = []
    allowed = (
        "event_type", "source", "play_id", "sequence_number",
        "source_event_time", "text", "team_id", "participant_ids",
        "period", "clock", "home_score", "away_score",
    )
    for event in value:
        if not isinstance(event, dict) or event.get("event_type") != "ejection":
            continue
        rows.append({
            **{key: event.get(key) for key in allowed},
            "received_at": received_at,
            "point_in_time": True,
            "evidence_only": True,
        })
    return tuple(rows)


def run_mispricing_sweep(
    markets: list[Any],
    forecast_fn: Callable[[Any], float | None],
    *,
    now_iso: str,
    book_fn: Callable[[Any], float | None] | None = None,
    opportunist: OpportunistEngine | None = None,
    edge_threshold: float = DEFAULT_EDGE_THRESHOLD,
    agree_margin: float = DEFAULT_AGREE_MARGIN,
    min_confidence: str = "medium",
    max_items: int = 25,
    specialist_fn: Callable[[Any], str | None] | None = None,
    divergence_fn: Callable[[Any], dict | None] | None = None,
    ejection_fn: Callable[[Any], Any] | None = None,
) -> dict[str, Any]:
    """Run one sweep; return a JSON-able report.

    Every market with a model view is assessed and (if an ``opportunist`` is
    given) observed so candidates lock and dips trigger across passes. The
    shortlist is the actionable, non-conflict assessments at or above
    ``min_confidence``, richest edge first, capped at ``max_items``.

    ``specialist_fn`` (WS-8, optional) returns the council specialist's own
    routing label (``Specialist.name`` -- e.g. "mlb", "crypto") for a
    market; when given, it tags the WS-8 ``entries`` this sweep also emits
    so ``autonomy.taxonomy.specialist_for`` resolves the CLV grader's
    ``(specialist, market_type)`` scope. A raising ``specialist_fn`` is
    caught per-market (fail-closed to an untagged "unknown" entry) so a
    broken router never wedges the pass.
    """
    monitor = MispricingMonitor(
        forecast_fn, book_fn,
        edge_threshold=edge_threshold, agree_margin=agree_margin,
        min_confidence=min_confidence,
    )
    scanned = 0
    assessed_pairs: list[tuple[Any, MispricingAssessment]] = []
    assessments_by_ticker: dict[str, MispricingAssessment] = {}
    source_by_ticker: dict[str, str | None] = {}
    divergence_by_ticker: dict[str, dict | None] = {}
    ejections_by_ticker: dict[str, tuple[dict[str, Any], ...]] = {}
    for market in markets:
        scanned += 1
        assessment = monitor.assess_market(market)
        if assessment is None:
            continue
        assessed_pairs.append((market, assessment))
        assessments_by_ticker[assessment.market_ticker] = assessment
        if specialist_fn is not None:
            try:
                source_by_ticker[assessment.market_ticker] = specialist_fn(market)
            except Exception:
                source_by_ticker[assessment.market_ticker] = None
        # CF1: attach the market's power-ratings divergence evidence, if any.
        # Fail-closed: a missing fn or a raising one leaves it absent (None),
        # byte-identical to the feature being off.
        if divergence_fn is not None:
            try:
                divergence_by_ticker[assessment.market_ticker] = divergence_fn(market)
            except Exception:
                divergence_by_ticker[assessment.market_ticker] = None
        # Live ejections are raw observations, not a fourth estimator. Attach
        # them after pricing so they cannot alter model/book/Kalshi math, and
        # stamp the monitor's receipt time for point-in-time provenance.
        if ejection_fn is not None:
            try:
                ejections_by_ticker[assessment.market_ticker] = _point_in_time_ejections(
                    ejection_fn(market), now_iso,
                )
            except Exception:
                ejections_by_ticker[assessment.market_ticker] = ()

    # WS-8: one book-tape row per assessed market (the full universe, not
    # just the shortlist -- CLV grading needs every ticker's price history).
    tape_rows = [_tape_row(market, assessment, now_iso) for market, assessment in assessed_pairs]

    # WS-5: group into per-game 3x3 lattices from the SAME markets/assessments
    # already computed above (no second fetch); a market that doesn't parse to
    # a sports contract simply isn't grouped (fail-closed).
    all_lattice_rows, tier_by_ticker = _lattice_section(
        [market for market, _ in assessed_pairs], assessments_by_ticker,
    )
    structural_count = sum(1 for row in all_lattice_rows if row["conviction_tier"] == TIER_STRUCTURAL)
    cross_confirmed_count = sum(
        1 for row in all_lattice_rows if row["conviction_tier"] == TIER_CROSS_CONFIRMED
    )
    lattice_rows = all_lattice_rows[:MAX_LATTICES]

    shortlist: list[MispricingAssessment] = []
    opportunities: list[dict[str, Any]] = []
    for market, assessment in assessed_pairs:
        tier = tier_by_ticker.get(assessment.market_ticker)
        if tier is not None:
            assessment = replace(assessment, conviction_tier=tier)
        divergence = divergence_by_ticker.get(assessment.market_ticker)
        if divergence is not None:
            assessment = replace(assessment, power_divergence=divergence)
        ejections = ejections_by_ticker.get(assessment.market_ticker, ())
        if ejections:
            assessment = replace(assessment, ejection_events=ejections)
        if opportunist is not None:
            opportunity = opportunist.observe(assessment)
            if opportunity is not None:
                opportunities.append(_opportunity_row(opportunity))
        if (
            assessment.side != "NONE"
            and assessment.agreement != "conflict"
            and monitor._meets_confidence(assessment.confidence)
        ):
            shortlist.append(assessment)

    shortlist.sort(key=lambda a: a.edge, reverse=True)
    top = shortlist[: max(0, int(max_items))]

    # WS-8: every shortlist + opportunist row, already computed above, cast
    # to the flat {ticker, side, entry_kalshi_prob, source, market_type, ts}
    # shape the CLV grader joins against the book tape. Nothing new is
    # priced here -- this just persists what the pass already decided.
    entries: list[dict[str, Any]] = []
    for a in top:
        row = _entry_row(
            a.market_ticker, a.side, a.market_prob,
            source_by_ticker.get(a.market_ticker), now_iso,
        )
        if row is not None:
            entries.append(row)
    for o in opportunities:
        row = _entry_row(
            o["ticker"], o["side"], o["entry_prob"],
            source_by_ticker.get(o["ticker"]), now_iso,
        )
        if row is not None:
            entries.append(row)

    return {
        "generated_at": now_iso,
        "scanned": scanned,
        "assessed": len(assessed_pairs),
        "shortlist_count": len(shortlist),
        "opportunity_count": len(opportunities),
        "shortlist": [_assessment_row(a) for a in top],
        "opportunities": opportunities,
        "lattices": lattice_rows,
        "structural_count": structural_count,
        "cross_confirmed_count": cross_confirmed_count,
        "tape_rows": tape_rows,
        "entries": entries,
        "params": {
            "edge_threshold": edge_threshold,
            "agree_margin": agree_margin,
            "min_confidence": min_confidence,
            "max_items": max_items,
        },
        "note": (
            "Challenger/paper evidence only. The sweep surfaces mispricing and "
            "opportunist strikes for review; it never places an order."
        ),
    }


# --------------------------------------------------------------------------
# WS-8 persistence: the runner script calls these right after a sweep to
# write the two evidence artifacts the CLV grader reads. run_mispricing_sweep
# itself stays pure (see module docstring); the I/O lives here instead so
# existing sweep tests never touch disk.
# --------------------------------------------------------------------------

def persist_book_tape(
    path: Path,
    report: dict[str, Any],
    *,
    last_by_ticker: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Append this pass's ``tape_rows`` to the book tape, deduped per ticker.

    Thin wrapper over ``autonomy.clv.append_tape_rows`` -- see that module
    for the dedup rule. Returns the updated last-row-per-ticker index so a
    long-running caller can carry it into the next pass without re-reading
    the file.
    """
    from autonomy.clv import append_tape_rows

    return append_tape_rows(path, report.get("tape_rows") or [], last_by_ticker=last_by_ticker)


def persist_paper_entries(path: Path, report: dict[str, Any]) -> int:
    """Append this pass's shortlist + opportunist ``entries`` as JSONL.

    Plain append, no dedup: a standing opportunist candidate or an
    unchanged shortlist edge legitimately re-appears pass after pass, and
    the CLV grader's per-event-cluster aggregation (autonomy/clv.py) is
    duplicate-invariant -- repeated identical clv_bps values within one
    cluster do not move that cluster's mean. Returns the row count written
    (0 when there is nothing to persist -- the file is left untouched, not
    created empty).
    """
    rows = report.get("entries") or []
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True))
            handle.write("\n")
    return len(rows)
