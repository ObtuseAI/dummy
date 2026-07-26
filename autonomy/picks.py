"""Picks-first accuracy layer (Wave-14, operator directive 2026-07-17:
"focus more on correct picks and probability and less on edge").

Everything upstream optimizes edge-vs-market. This module measures the thing
the operator actually asked for: is the FUSED probability RIGHT about
outcomes? Two pieces:

1. ``build_fused_signal`` -- the brain records its final quantitative fused
   probability after debate observations are recorded
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

3. ``apply_promoted_fused_calibration`` -- the only post-fusion correction
   path. A content-validated map still emits a shadow; the traded probability
   changes only when the exact ``fused_forecast::cal`` scope independently
   clears the existing promotion registry.

This module never writes promotion state or creates execution authority.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from autonomy.ontology import Forecast, Signal
from autonomy.sports_markets import spec_for

FUSED_SOURCE = "fused_forecast"

# Probabilities this close to a coin flip are "no pick": they still grade for
# Brier/calibration but are excluded from the hit-rate numerator/denominator
# (calling 0.501 a "pick" would launder noise into the accuracy number).
NO_PICK_BAND = 0.02

CALIBRATION_BINS = 10


@dataclass(frozen=True)
class FusedCalibrationEvidence:
    """Validated reliability maps that may produce fused calibration shadows."""

    maps: dict[str, list[tuple[float, float]]]
    maps_sha256: str

    def __post_init__(self) -> None:
        digest = str(self.maps_sha256)
        if (
            not self.maps
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or any(
                not str(scope).startswith(f"{FUSED_SOURCE}|") or not knots
                for scope, knots in self.maps.items()
            )
        ):
            raise ValueError("invalid fused calibration evidence")


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
            # Wave-78: carry the independent model view so the display-refresh /
            # ledger-fallback board path can surface it without the live
            # signals. Display-only; never touches the traded probability.
            "model_probability_yes": getattr(
                forecast, "model_probability_yes", None),
            "model_uncertainty": getattr(forecast, "model_uncertainty", None),
            "model_sources": (
                dict(forecast.model_sources)
                if getattr(forecast, "model_sources", None) else None
            ),
            **tier_features,
        },
    )


def load_fused_maps() -> dict[str, Any]:
    """The nightly reliability maps, filtered to fused-forecast scopes.

    Fail-closed: a missing/malformed artifact means no maps, which means no
    calibrated shadow rows -- never an error in the cycle path."""
    evidence = load_fused_calibration_evidence()
    return {} if evidence is None else dict(evidence.maps)


def load_fused_calibration_evidence(
    path: Path | None = None,
) -> FusedCalibrationEvidence | None:
    """Load only content-validated fused maps, fail-closed on any defect."""

    from autonomy.reliability import ReliabilityMaps

    loaded = ReliabilityMaps(path)
    if loaded.artifact_sha256 is None:
        return None
    maps: dict[str, list[tuple[float, float]]] = {}
    for scope in loaded.scopes():
        if not scope.startswith(f"{FUSED_SOURCE}|"):
            continue
        knots = loaded.knots_for(scope)
        if knots:
            maps[scope] = knots
    if not maps:
        return None
    try:
        return FusedCalibrationEvidence(
            maps=maps,
            maps_sha256=loaded.artifact_sha256,
        )
    except ValueError:
        return None


def build_calibrated_fused_signal(
    market_ticker: str,
    forecast: Any,
    maps: dict[str, Any],
    tier_assessment: Any | None = None,
    *,
    maps_sha256: str | None = None,
) -> Signal | None:
    """The SHADOW calibrated fused row (``fused_forecast::cal``), or None
    when no reliability map covers this market's fused scope yet.

    A monotone transform of the raw fused row, graded under its own source
    axis so raw-vs-calibrated is measured head-to-head on settlements before
    the correction is ever allowed near the decision path (the same
    discipline as the WS-18 per-source ::cal challengers)."""
    if not maps:
        return None
    from autonomy.reliability import (
        CALIBRATION_GATE_VERSION,
        CALIBRATION_MAP_VERSION,
        apply_reliability,
    )
    from autonomy.taxonomy import grading_scope

    raw = build_fused_signal(market_ticker, forecast, tier_assessment)
    scope = grading_scope(FUSED_SOURCE, market_ticker, raw.features)
    knots = maps.get(scope)
    if not knots:
        return None
    corrected = apply_reliability(
        [tuple(k) for k in knots], raw.probability_yes)
    features = {
        **raw.features,
        "challenger_only": True,
        "calibration_map_version": CALIBRATION_MAP_VERSION,
        "calibration_scope": scope,
        "calibrated_scope": scope,
        "calibrated_from": FUSED_SOURCE,
        "raw_probability": raw.probability_yes,
        "raw_probability_yes": raw.probability_yes,
    }
    if maps_sha256 is not None:
        features["calibration_gate"] = {
            "version": CALIBRATION_GATE_VERSION,
            "scope": scope,
            "maps_sha256": maps_sha256,
            "cluster_isolated_holdout": True,
            "strict_brier_improvement": True,
        }
    return Signal(
        source=f"{FUSED_SOURCE}::cal",
        market_ticker=market_ticker,
        probability_yes=corrected,
        uncertainty=raw.uncertainty,
        rationale=f"calibrated {raw.probability_yes:.3f}->{corrected:.3f} ({scope})",
        features=features,
    )


def apply_promoted_fused_calibration(
    market_ticker: str,
    forecast: Forecast,
    evidence: FusedCalibrationEvidence | None,
    promotion: Any,
    tier_assessment: Any | None = None,
) -> Forecast:
    """Return a calibrated traded forecast only after the exact evidence gate.

    A validated map merely creates a shadow challenger.  The raw forecast is
    returned unless that exact ``fused_forecast::cal`` scope is independently
    active in the promotion registry; this function never writes promotion
    state and never treats map fitting as promotion evidence.
    """

    if evidence is None:
        return forecast
    calibrated = build_calibrated_fused_signal(
        market_ticker,
        forecast,
        evidence.maps,
        tier_assessment,
        maps_sha256=evidence.maps_sha256,
    )
    if calibrated is None:
        return forecast
    is_promoted = getattr(promotion, "is_promoted_signal", None)
    if not callable(is_promoted) or not is_promoted(
        calibrated.source,
        market_ticker,
        calibrated.features,
    ):
        return forecast
    implied = getattr(forecast, "market_implied_yes", None)
    edge = (
        calibrated.probability_yes - float(implied)
        if implied is not None
        else 0.0
    )
    return replace(
        forecast,
        probability_yes=calibrated.probability_yes,
        edge_yes=edge,
        # Attribute the traded transform itself. The raw fused row (recorded
        # immediately before this gate) preserves its complete underlying
        # source weights, while this single-source attribution lets settled
        # decisions grade and demote the promoted calibration honestly.
        sources_used={calibrated.source: 1.0},
        rationale=(
            f"{forecast.rationale}; promoted {calibrated.source} "
            f"{forecast.probability_yes:.3f}->{calibrated.probability_yes:.3f}"
        )[:600],
        calibration_source=calibrated.source,
        uncalibrated_probability_yes=float(forecast.probability_yes),
        calibration_scope=str(calibrated.features["calibrated_scope"]),
        calibration_evidence_sha256=evidence.maps_sha256,
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

    Installs the ``signal_history`` union view itself: it is a per-CONNECTION
    temp view, and this is an entry point (callers reach it before
    ``live_picks_for_settled_markets``), so relying on another function to have
    installed it is what made this path fail with "no such table:
    signal_history" until the 2026-07-24 failure rail exposed it.
    """
    from autonomy.retention import ensure_signal_history

    ensure_signal_history(conn)
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
