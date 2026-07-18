"""Picks-first accuracy layer (Wave-14, operator directive 2026-07-17:
"focus more on correct picks and probability and less on edge").

Everything upstream optimizes edge-vs-market. This module measures the thing
the operator actually asked for: is the FUSED probability RIGHT about
outcomes? Two pieces:

1. ``build_fused_signal`` -- the brain records its FINAL post-debate fused
   probability for every scored market as a first-class ledger row
   (source=``fused_forecast``). Until now the fused number lived only inside
   traded decisions, so the machine's actual opinion was unmeasurable on the
   ~99% of markets it never traded. The row is marked
   ``challenger_only=False`` (it is the OUTPUT, not a candidate: the
   promotion ladder's challenger gate therefore never sees it) and it is
   never fed back into fusion (fusion consumes registry signals, not ledger
   rows).

2. ``grade_source_picks`` / ``pick_accuracy_report`` -- outcome-grounded
   grading: hit rate on the picked side, absolute Brier, and a 10-bin
   calibration table, overall and broken down by (league, market_type) via
   the ticker registry. No market benchmark enters anywhere, which makes
   this measurement immune by construction to the fabricated-benchmark
   class of bug (Wave-5): the ground truth is the settlement, full stop.

Read-only against the ledger except for the brain's one record call.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from autonomy.ontology import Signal
from autonomy.sports_markets import spec_for

FUSED_SOURCE = "fused_forecast"

# Probabilities this close to a coin flip are "no pick": they still grade for
# Brier/calibration but are excluded from the hit-rate numerator/denominator
# (calling 0.501 a "pick" would launder noise into the accuracy number).
NO_PICK_BAND = 0.02

CALIBRATION_BINS = 10


def build_fused_signal(market_ticker: str, forecast: Any) -> Signal:
    """The fused forecast as a persistable ledger row."""
    return Signal(
        source=FUSED_SOURCE,
        market_ticker=market_ticker,
        probability_yes=float(forecast.probability_yes),
        uncertainty=float(forecast.uncertainty),
        rationale=f"fused: {forecast.rationale}"[:300],
        features={
            "challenger_only": False,
            "is_fused_output": True,
            "market_implied_yes": forecast.market_implied_yes,
            "edge_yes": forecast.edge_yes,
            "sources_used": dict(forecast.sources_used),
        },
    )


def _scope_of(ticker: str) -> tuple[str, str]:
    """(league, market_type) from the series registry; crypto/econ tickers
    fall to ("other", "other") rather than being dropped."""
    spec = spec_for(ticker)
    if spec is None:
        return "other", "other"
    return spec.league, spec.market_type


def latest_settled_emissions(
    conn: sqlite3.Connection, source: str, days: float | None = None,
) -> list[tuple[str, float, bool]]:
    """[(ticker, probability_yes, result_yes)] using the LAST emission per
    settled market -- the pick of record is the final pre-settlement opinion."""
    from autonomy.retention import install_signal_history

    install_signal_history(conn)
    clause = ""
    params: list[Any] = [source]
    if days is not None:
        clause = " AND s.created_at >= datetime('now', ?)"
        params.append(f"-{float(days)} days")
    rows = conn.execute(
        f"""
        SELECT s.market_ticker, s.probability_yes, s.created_at, st.result_yes
        FROM signal_history s
        JOIN settlements st ON st.market_ticker = s.market_ticker
        WHERE s.source = ?{clause}
        """,
        params,
    ).fetchall()
    latest: dict[str, tuple[str, float, bool]] = {}
    for ticker, probability, created_at, result_yes in rows:
        ticker = str(ticker)
        held = latest.get(ticker)
        if held is None or str(created_at) > held[0]:
            latest[ticker] = (str(created_at), float(probability), bool(result_yes))
    return [(t, p, y) for t, (_, p, y) in sorted(latest.items())]


def grade_picks(
    emissions: list[tuple[str, float, bool]],
) -> dict[str, Any]:
    """Outcome-grounded accuracy for one emission set (no market benchmark)."""
    n = len(emissions)
    if n == 0:
        return {"n": 0}
    brier = sum((p - (1.0 if y else 0.0)) ** 2 for _, p, y in emissions) / n
    picks = [
        (p, y) for _, p, y in emissions if abs(p - 0.5) > NO_PICK_BAND
    ]
    hits = sum(1 for p, y in picks if (p >= 0.5) == y)
    bins: list[dict[str, Any]] = []
    for b in range(CALIBRATION_BINS):
        lo, hi = b / CALIBRATION_BINS, (b + 1) / CALIBRATION_BINS
        members = [
            (p, y) for _, p, y in emissions
            if (lo <= p < hi) or (b == CALIBRATION_BINS - 1 and p == hi)
        ]
        if not members:
            continue
        bins.append({
            "bin": f"{lo:.1f}-{hi:.1f}",
            "n": len(members),
            "predicted_mean": round(sum(p for p, _ in members) / len(members), 4),
            "realized_rate": round(
                sum(1 for _, y in members if y) / len(members), 4),
        })
    return {
        "n": n,
        "brier": round(brier, 5),
        "picks": len(picks),
        "no_pick": n - len(picks),
        "hit_rate": round(hits / len(picks), 4) if picks else None,
        "calibration": bins,
    }


def grade_source_picks(
    conn: sqlite3.Connection, source: str = FUSED_SOURCE, days: float | None = 90.0,
) -> dict[str, Any]:
    """Overall + per-(league, market_type) pick accuracy for one source."""
    emissions = latest_settled_emissions(conn, source, days=days)
    overall = grade_picks(emissions)
    by_scope: dict[str, list[tuple[str, float, bool]]] = {}
    for ticker, probability, result in emissions:
        league, market_type = _scope_of(ticker)
        by_scope.setdefault(f"{league}|{market_type}", []).append(
            (ticker, probability, result))
    return {
        "source": source,
        "window_days": days,
        "overall": overall,
        "by_scope": {
            scope: grade_picks(rows)
            for scope, rows in sorted(by_scope.items())
            if len(rows) >= 5      # tiny cells are noise, not evidence
        },
    }


def pick_accuracy_report(
    conn: sqlite3.Connection,
    sources: tuple[str, ...] = (FUSED_SOURCE,),
    days: float | None = 90.0,
) -> dict[str, Any]:
    """The nightly picks section: fused first, any extra sources after."""
    return {
        "focus": "correct picks and probability (operator directive 2026-07-17)",
        "sources": [grade_source_picks(conn, source, days=days) for source in sources],
    }
