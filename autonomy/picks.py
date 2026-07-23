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


def build_fused_signal(
    market_ticker: str,
    forecast: Any,
    tier_assessment: Any | None = None,
) -> Signal:
    """The fused forecast as a persistable ledger row."""
    tier_features: dict[str, Any] = {}
    if tier_assessment is not None:
        try:
            tier_features = dict(tier_assessment.feature_fields())
        except (AttributeError, TypeError, ValueError):
            tier_features = {}
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
            **tier_features,
        },
    )


def load_fused_maps() -> dict[str, Any]:
    """The nightly reliability maps, filtered to fused-forecast scopes.

    Fail-closed: a missing/malformed artifact means no maps, which means no
    calibrated shadow rows -- never an error in the cycle path."""
    import json

    from autonomy.reliability import DEFAULT_MAPS_PATH

    try:
        payload = json.loads(DEFAULT_MAPS_PATH.read_text(encoding="utf-8"))
        maps = payload.get("maps") or {}
    except (OSError, ValueError, TypeError):
        return {}
    return {
        scope: knots for scope, knots in maps.items()
        if str(scope).startswith(f"{FUSED_SOURCE}|") and knots
    }


def build_calibrated_fused_signal(
    market_ticker: str,
    forecast: Any,
    maps: dict[str, Any],
    tier_assessment: Any | None = None,
) -> Signal | None:
    """The SHADOW calibrated fused row (``fused_forecast::cal``), or None
    when no reliability map covers this market's fused scope yet.

    A monotone transform of the raw fused row, graded under its own source
    axis so raw-vs-calibrated is measured head-to-head on settlements before
    the correction is ever allowed near the decision path (the same
    discipline as the WS-18 per-source ::cal challengers)."""
    if not maps:
        return None
    from autonomy.reliability import apply_reliability
    from autonomy.taxonomy import grading_scope

    raw = build_fused_signal(market_ticker, forecast, tier_assessment)
    scope = grading_scope(FUSED_SOURCE, market_ticker, raw.features)
    knots = maps.get(scope)
    if not knots:
        return None
    corrected = apply_reliability(
        [tuple(k) for k in knots], raw.probability_yes)
    return Signal(
        source=f"{FUSED_SOURCE}::cal",
        market_ticker=market_ticker,
        probability_yes=corrected,
        uncertainty=raw.uncertainty,
        rationale=f"calibrated {raw.probability_yes:.3f}->{corrected:.3f} ({scope})",
        features={
            **raw.features,
            "calibration_scope": scope,
            "raw_probability": raw.probability_yes,
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
    """Return one canonical live pick per settled market.

    The pick of record is the latest source emission that was both created
    and received no later than settlement and, when present, the earliest
    decision. Retro rows and malformed provenance never become live evidence.
    """
    import math

    from autonomy.retention import install_signal_history
    from autonomy.strategy_miner import _parse_ts

    install_signal_history(conn)
    has_decisions = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='decisions'"
    ).fetchone() is not None
    decision_times: dict[str, float | None] = {}
    if has_decisions:
        for ticker, created_at in conn.execute(
            "SELECT market_ticker, created_at FROM decisions"
        ):
            key = str(ticker)
            stamp = _parse_ts(created_at)
            if stamp is None:
                decision_times[key] = None
            elif key not in decision_times:
                decision_times[key] = stamp
            elif decision_times[key] is not None:
                decision_times[key] = min(float(decision_times[key]), stamp)

    clause = ""
    params: list[Any] = [source]
    if days is not None:
        clause = " AND julianday(s.created_at) >= julianday('now', ?)"
        params.append(f"-{float(days)} days")
    rows = conn.execute(
        f"""
        SELECT s.id, s.market_ticker, s.probability_yes, s.created_at,
               s.ingested_at, s.mode, st.result_yes, st.settled_at
        FROM signal_history s
        JOIN settlements st ON st.market_ticker = s.market_ticker
        WHERE s.source = ? AND LOWER(s.mode) = 'live'{clause}
        """,
        params,
    ).fetchall()
    latest: dict[str, tuple[tuple[float, float, int], float, bool]] = {}
    for (
        row_id,
        ticker,
        probability,
        created_at,
        ingested_at,
        mode,
        result_yes,
        settled_at,
    ) in rows:
        ticker = str(ticker)
        if str(mode).strip().lower() != "live":
            continue
        created_ts = _parse_ts(created_at)
        ingested_ts = _parse_ts(ingested_at)
        settled_ts = _parse_ts(settled_at)
        if created_ts is None or ingested_ts is None or settled_ts is None:
            continue
        if ingested_ts < created_ts:
            continue
        cutoff_ts = settled_ts
        if ticker in decision_times:
            decision_ts = decision_times[ticker]
            if decision_ts is None:
                continue
            cutoff_ts = min(cutoff_ts, decision_ts)
        if created_ts > cutoff_ts or ingested_ts > cutoff_ts:
            continue
        try:
            parsed_probability = float(probability)
            outcome = float(result_yes)
        except (TypeError, ValueError):
            continue
        if (
            not math.isfinite(parsed_probability)
            or not 0.0 <= parsed_probability <= 1.0
            or not math.isfinite(outcome)
            or outcome not in (0.0, 1.0)
        ):
            continue
        rank = (created_ts, ingested_ts, int(row_id))
        held = latest.get(ticker)
        if held is None or rank > held[0]:
            latest[ticker] = (rank, parsed_probability, bool(outcome))
    return [
        (ticker, probability, result)
        for ticker, (_rank, probability, result) in sorted(latest.items())
    ]


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


def llm_voice_sources(
    conn: sqlite3.Connection, *, days: float | None = 90.0, limit: int = 12,
) -> tuple[str, ...]:
    """Distinct settled LLM panel/debate sources, most-recent first.

    Every sealed panel opinion is already graded per settlement under a
    stable per-voice source (``llm_panel_v3_{provider}_{digest}`` plus the
    bounded ``llm_debate`` aggregate); this surfaces which voices exist so
    the nightly picks report can grade each one. Observational only.
    """
    clause = ""
    params: list[Any] = []
    if days is not None:
        clause = " AND s.created_at >= datetime('now', ?)"
        params.append(f"-{float(days)} day")
    rows = conn.execute(
        "SELECT s.source, MAX(s.created_at) AS latest FROM signal_history s"
        " JOIN settlements t ON t.market_ticker = s.market_ticker"
        " WHERE (s.source LIKE 'llm_panel%' OR s.source LIKE 'llm_debate%')"
        + clause +
        " GROUP BY s.source ORDER BY latest DESC LIMIT ?",
        (*params, int(limit)),
    ).fetchall()
    return tuple(str(row[0]) for row in rows)
