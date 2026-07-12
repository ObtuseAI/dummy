"""Mispricing sweep: one buy-low/opportunist pass over a batch of markets.

Ties the pieces together into a single, testable pass — the body of the
dedicated fast monitor loop (P2b):

  scan -> our fused forecast (model_prob) -> de-vigged book (book_prob, sports)
       -> triangulated MispricingAssessment -> OpportunistEngine (patience)
       -> a JSON-able report the dashboard renders.

Pure and injectable: the caller supplies the market list, a ``forecast_fn``
(our model's probability for a market; None -> skip, fail-closed), an optional
``book_fn`` (de-vigged sportsbook probability), and an optional stateful
``OpportunistEngine`` carried across passes. No I/O here; the runner script
does the scanning, persistence, and scheduling.

Everything downstream is challenger / paper evidence — the sweep never places
an order; it surfaces the shortlist and the opportunist strikes for review.
"""
from __future__ import annotations

from dataclasses import replace
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

# Report caps: at most this many per-game lattice rows, richest tier first.
MAX_LATTICES = 20


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
    }


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
) -> dict[str, Any]:
    """Run one sweep; return a JSON-able report.

    Every market with a model view is assessed and (if an ``opportunist`` is
    given) observed so candidates lock and dips trigger across passes. The
    shortlist is the actionable, non-conflict assessments at or above
    ``min_confidence``, richest edge first, capped at ``max_items``.
    """
    monitor = MispricingMonitor(
        forecast_fn, book_fn,
        edge_threshold=edge_threshold, agree_margin=agree_margin,
        min_confidence=min_confidence,
    )
    scanned = 0
    assessed_pairs: list[tuple[Any, MispricingAssessment]] = []
    assessments_by_ticker: dict[str, MispricingAssessment] = {}
    for market in markets:
        scanned += 1
        assessment = monitor.assess_market(market)
        if assessment is None:
            continue
        assessed_pairs.append((market, assessment))
        assessments_by_ticker[assessment.market_ticker] = assessment

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
