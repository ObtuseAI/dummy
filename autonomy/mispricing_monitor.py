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

from typing import Any, Callable

from autonomy.mispricing import (
    DEFAULT_AGREE_MARGIN,
    DEFAULT_EDGE_THRESHOLD,
    MispricingAssessment,
    MispricingMonitor,
)
from autonomy.opportunist import OpportunistEngine, Opportunity


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
    shortlist: list[MispricingAssessment] = []
    opportunities: list[dict[str, Any]] = []
    scanned = 0
    assessed = 0
    for market in markets:
        scanned += 1
        assessment = monitor.assess_market(market)
        if assessment is None:
            continue
        assessed += 1
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
        "assessed": assessed,
        "shortlist_count": len(shortlist),
        "opportunity_count": len(opportunities),
        "shortlist": [_assessment_row(a) for a in top],
        "opportunities": opportunities,
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
