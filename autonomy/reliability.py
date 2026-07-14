"""Reliability calibration — challenger-shaped isotonic recalibration.

Council build-out WS-18 (global floor raiser). A source can be sharp yet
mis-calibrated: it says 0.90 and wins 0.75. This layer learns each well-
sampled scope's reliability curve from settled history and re-emits the
parent's forecast with the miscalibration corrected -- but ONLY as a
challenger. The corrected view (``{source}::cal``) is graded head-to-head
against its parent; it reaches execution only if WS-14 promotes it.

  * Cluster-weighted 10-bin reliability curve (predicted vs realized) made
    monotone by pool-adjacent-violators (isotonic-lite) -- a probability
    can only be corrected up if a higher prediction realized higher.
  * A scope needs >= MIN_CALIBRATION_CLUSTERS independent event-clusters or
    it gets NO map (the wrapper abstains -- fail-closed, never a guess).
  * Nothing is silently recalibrated: maps live in a reviewable artifact and
    the correction only ever flows through the challenger wrapper.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from autonomy.ontology import MarketView, Signal
from autonomy.taxonomy import grading_scope

DEFAULT_MAPS_PATH = Path("runtime/autonomy/reliability_maps.json")
MIN_CALIBRATION_CLUSTERS = 200
CALIBRATION_BINS = 10
CALIBRATION_MAP_VERSION = 1

# Curated rollout (emitted source strings), not auto-everything: the crypto
# champion + challenger and the two largest MLB scopes.
CALIBRATED_SOURCES = frozenset({
    "crypto_spot_vol",
    "crypto_ewma_t",
    "mlb_structural_winner",
    "mlb_total_runs",
})

Knot = tuple[float, float]  # (predicted, calibrated)


def _pav_isotonic(values: list[float], weights: list[float]) -> list[float]:
    """Pool-adjacent-violators: nearest non-decreasing weighted fit."""
    blocks: list[list[float]] = []  # [sum_wy, sum_w, count]
    for value, weight in zip(values, weights):
        blocks.append([value * weight, weight, 1.0])
        while len(blocks) >= 2 and (
            blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]
        ):
            wy, w, count = blocks.pop()
            blocks[-1][0] += wy
            blocks[-1][1] += w
            blocks[-1][2] += count
    fitted: list[float] = []
    for wy, w, count in blocks:
        fitted.extend([wy / w] * int(count))
    return fitted


def fit_reliability_map(
    pairs: Iterable[tuple[float, float, str]],
    *,
    bins: int = CALIBRATION_BINS,
    min_clusters: int = MIN_CALIBRATION_CLUSTERS,
) -> list[Knot] | None:
    """Fit a monotone reliability map, or None when under-sampled.

    ``pairs`` are ``(predicted, outcome_0_or_1, event_cluster)``. Correlated
    emissions in one cluster collapse to that cluster's mean prediction and
    mean outcome (one unit of evidence), so the curve reflects independent
    events, not repeated strikes.
    """
    cluster_pred: dict[str, list[float]] = {}
    cluster_out: dict[str, list[float]] = {}
    for predicted, outcome, cluster in pairs:
        cluster_pred.setdefault(cluster, []).append(float(predicted))
        cluster_out.setdefault(cluster, []).append(float(outcome))
    clusters = list(cluster_pred)
    if len(clusters) < min_clusters:
        return None
    points = [
        (sum(cluster_pred[c]) / len(cluster_pred[c]),
         sum(cluster_out[c]) / len(cluster_out[c]))
        for c in clusters
    ]
    # Bin cluster points by predicted probability into equal-width bins.
    binned: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    for pred, out in points:
        index = min(bins - 1, max(0, int(pred * bins)))
        binned[index].append((pred, out))
    bin_pred: list[float] = []
    bin_out: list[float] = []
    bin_weight: list[float] = []
    for bucket in binned:
        if not bucket:
            continue
        bin_pred.append(sum(p for p, _o in bucket) / len(bucket))
        bin_out.append(sum(o for _p, o in bucket) / len(bucket))
        bin_weight.append(float(len(bucket)))
    if len(bin_pred) < 2:
        return None  # not enough spread to define a curve
    calibrated = _pav_isotonic(bin_out, bin_weight)
    return [(round(p, 6), round(min(1.0, max(0.0, c)), 6))
            for p, c in zip(bin_pred, calibrated)]


def apply_reliability(knots: list[Knot] | None, probability: float) -> float:
    """Piecewise-linear correction; flat outside the knot range; clamped."""
    if not knots:
        return probability
    p = float(probability)
    if p <= knots[0][0]:
        corrected = knots[0][1]
    elif p >= knots[-1][0]:
        corrected = knots[-1][1]
    else:
        corrected = knots[-1][1]
        for (p0, c0), (p1, c1) in zip(knots, knots[1:]):
            if p0 <= p <= p1:
                span = p1 - p0
                corrected = c0 if span <= 0 else c0 + (c1 - c0) * (p - p0) / span
                break
    return min(0.995, max(0.005, corrected))


def fit_maps_from_rows(
    rows: Iterable[Any],
    *,
    sources: frozenset[str] = CALIBRATED_SOURCES,
) -> dict[str, list[Knot]]:
    """Fit a reliability map per grading scope for the curated sources.

    ``rows`` are miner MinedRow-likes (need ``source``, ``ticker``,
    ``features``, ``probability_yes``, ``result_yes``, ``event_cluster``,
    ``scope``). Only scopes reaching the cluster minimum get a map.
    """
    grouped: dict[str, list[tuple[float, float, str]]] = {}
    for row in rows:
        if str(getattr(row, "source", "")) not in sources:
            continue
        scope = getattr(row, "scope", "") or grading_scope(
            row.source, row.ticker, getattr(row, "features", {}) or {})
        grouped.setdefault(scope, []).append(
            (float(row.probability_yes), 1.0 if row.result_yes else 0.0,
             str(row.event_cluster)))
    maps: dict[str, list[Knot]] = {}
    for scope, pairs in grouped.items():
        knots = fit_reliability_map(pairs)
        if knots is not None:
            maps[scope] = knots
    return maps


class ReliabilityMaps:
    """Loads the per-scope reliability maps artifact (fail-closed)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or DEFAULT_MAPS_PATH)
        self._maps: dict[str, list[Knot]] = {}
        self.reload()

    def reload(self) -> None:
        self._maps = {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return
        for scope, knots in (raw.get("maps") or {}).items():
            try:
                self._maps[str(scope)] = [(float(p), float(c)) for p, c in knots]
            except (TypeError, ValueError):
                continue

    def correct(self, scope: str, probability: float) -> float | None:
        """Corrected probability for a scope, or None when no map exists."""
        knots = self._maps.get(scope)
        if knots is None:
            return None
        return apply_reliability(knots, probability)

    def scopes(self) -> list[str]:
        return sorted(self._maps)


class CalibratedSignal:
    """Challenger wrapper: re-emits a parent's forecast, isotonic-corrected.

    Only opines for curated sources at scopes that have a map; everywhere
    else it abstains, so the parent's uncorrected view is untouched.
    """

    def __init__(
        self,
        parent: Any,
        maps: ReliabilityMaps | None = None,
        sources: frozenset[str] = CALIBRATED_SOURCES,
    ) -> None:
        self.parent = parent
        self.maps = maps or ReliabilityMaps()
        self.sources = sources
        self.name = f"{getattr(parent, 'name', 'source')}::cal"
        self._circuit_open = False

    def applicable(self, market: MarketView) -> bool:
        try:
            return bool(self.parent.applicable(market))
        except Exception:
            return False

    def on_cycle_start(self) -> None:
        # The parent (shared instance) is warmed by its own registration; the
        # wrapper only needs its map artifact fresh for the coming cycle.
        self._circuit_open = False
        self.maps.reload()

    def generate(self, market: MarketView) -> Signal | None:
        # Per-cycle circuit breaker: the wrapper re-invokes parent.generate,
        # which the registry's own health-quarantine can't shield. If the
        # parent raises once (a data outage, not a per-market abstain -- those
        # return None), skip it for the rest of the cycle so one wrapper cannot
        # trigger an unbounded storm of failing fetches across every market.
        if self._circuit_open:
            return None
        try:
            signal = self.parent.generate(market)
        except Exception:
            self._circuit_open = True
            return None
        if signal is None or signal.source not in self.sources:
            return None
        scope = grading_scope(signal.source, market.ticker, signal.features or {})
        corrected = self.maps.correct(scope, signal.probability_yes)
        if corrected is None:
            return None  # no map for this scope -> abstain (parent stands)
        features = {
            **(signal.features or {}),
            "challenger_only": True,
            "calibration_map_version": CALIBRATION_MAP_VERSION,
            "calibrated_from": signal.source,
            "raw_probability_yes": signal.probability_yes,
        }
        return Signal(
            source=f"{signal.source}::cal",
            market_ticker=market.ticker,
            probability_yes=corrected,
            uncertainty=signal.uncertainty,
            rationale=f"calibrated {signal.source}: {signal.probability_yes:.3f}->{corrected:.3f}",
            features=features,
        )
