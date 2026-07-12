"""Reverse-engineer edges from past and missed trades (Phase 1c).

Operator directive 2026-07-12: dummy should be able to reverse-engineer
trading strategies/indicators from past/missed trades.

The ledger already holds everything needed, point-in-time and settlement-
graded: every signal a source ever emitted (``signals``, features JSON --
including all the setups the system did NOT act on), the market's own
contemporaneous price (the ``market_prior`` source), and ground truth
(``settlements``). This miner searches a BOUNDED, auditable predicate space
over those recorded feature states for conditions under which a source's
forecasts carried real edge against the market -- then writes a proposal
artifact for review.

Discipline (propose-then-promote, spec section 3.4):
  * The miner never changes live behavior. Its output is a JSON artifact of
    candidate rules with train/test evidence; adopting one is an explicit,
    human-reviewed governance action (a rule would ship as a challenger
    first regardless).
  * Bounded predicate families only -- tercile thresholds on a curated
    feature list and depth-2 conjunctions, capped in count. No free-form
    strategy generation, no unbounded data dredging.
  * Walk-forward honesty: thresholds are fit on the TRAIN fold only; a rule
    must hold out-of-sample (chronologically later data) with a minimum
    sample and a CI95 lower bound above zero to be a candidate.
  * Event-cluster purging: rows sharing an event cluster (the ticker's
    event prefix) never straddle the train/test boundary as duplicates --
    the same underlying event cannot vouch for itself.
"""
from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autonomy.stats import mean_ci95

# Feature paths mined for numeric threshold predicates. Curated: every entry
# is a point-in-time, settlement-independent quantity a signal actually logs.
NUMERIC_FEATURES = (
    "setup_score",
    "mtf_alignment",
    "technical_score",
    "vol_regime_ratio",
    "rsi_14m",
    "hourly_rsi_14h",
    "shift_in_horizon_sigma",
    "horizon_log_return_sigma",
    "hours_to_close",
    "top_book_imbalance",
    "momentum_60m_bps",
    "volume_surge_15m",
)
MIN_TRAIN_SAMPLES = 30
MIN_TEST_SAMPLES = 20
# Correlated emissions (many rows per market, sibling strikes per event)
# would make a per-row CI dishonestly tight; the CI is therefore computed
# over per-event-cluster mean edges, and needs this many clusters.
MIN_TEST_CLUSTERS = 10
MAX_CANDIDATE_RULES = 500
MATCH_WINDOW_MINUTES = 15.0


def _parse_ts(text: str) -> float | None:
    from datetime import datetime as _dt

    try:
        return _dt.fromisoformat(str(text).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


@dataclass(frozen=True)
class MinedRow:
    """One settled, market-benchmarked signal emission."""

    source: str
    ticker: str
    event_cluster: str
    created_at: str
    probability_yes: float
    market_probability: float
    result_yes: bool
    features: dict[str, Any]
    # Grading scope (source|market_type|horizon_or_phase) so mined rules can
    # be read per-scope, consistent with the backtest's per-scope trackers.
    scope: str = ""


@dataclass(frozen=True)
class Predicate:
    feature: str
    op: str  # "<=" | ">"
    threshold: float

    def matches(self, row: MinedRow) -> bool:
        value = row.features.get(self.feature)
        if value is None:
            return False
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        return number <= self.threshold if self.op == "<=" else number > self.threshold

    def describe(self) -> str:
        return f"{self.feature} {self.op} {self.threshold:.4g}"


@dataclass(frozen=True)
class Rule:
    predicates: tuple[Predicate, ...]

    def matches(self, row: MinedRow) -> bool:
        return all(predicate.matches(row) for predicate in self.predicates)

    def describe(self) -> str:
        return " AND ".join(predicate.describe() for predicate in self.predicates)


@dataclass
class RuleEvidence:
    rule: str
    n_train: int
    n_test: int
    train_edge: float
    test_edge: float
    test_ci95_low: float
    test_ci95_high: float
    verdict: str
    detail: dict[str, Any] = field(default_factory=dict)


def _brier_edge(row: MinedRow) -> float:
    """Per-row edge: market Brier minus source Brier (positive = sharper)."""
    outcome = 1.0 if row.result_yes else 0.0
    market_brier = (row.market_probability - outcome) ** 2
    model_brier = (row.probability_yes - outcome) ** 2
    return market_brier - model_brier


def load_settled_rows(
    conn: sqlite3.Connection,
    *,
    sources: tuple[str, ...] | None = None,
    window_minutes: float = MATCH_WINDOW_MINUTES,
) -> list[MinedRow]:
    """Settled signal rows joined to the contemporaneous market prior.

    A row qualifies only when a ``market_prior`` emission exists for the
    same market within ``window_minutes`` of the signal -- the benchmark
    must be point-in-time, not hindsight.
    """
    # Nearest-in-time market_prior match is done in Python: SQLite rejects
    # outer references inside a subquery's ORDER BY, and a flat two-query
    # plus bisect approach is deterministic and easy to audit.
    import bisect

    _ts = _parse_ts
    priors: dict[str, list[tuple[float, float]]] = {}
    for ticker, created_at, probability in conn.execute(
        "SELECT market_ticker, created_at, probability_yes FROM signals"
        " WHERE source = 'market_prior'",
    ):
        stamp = _ts(created_at)
        if stamp is not None:
            priors.setdefault(str(ticker), []).append((stamp, float(probability)))
    for series in priors.values():
        series.sort()

    def _nearest_prior(ticker: str, stamp: float) -> float | None:
        series = priors.get(ticker)
        if not series:
            return None
        stamps = [entry[0] for entry in series]
        index = bisect.bisect_left(stamps, stamp)
        best: tuple[float, float] | None = None
        for candidate in (index - 1, index):
            if 0 <= candidate < len(series):
                gap = abs(series[candidate][0] - stamp)
                if best is None or gap < best[0]:
                    best = (gap, series[candidate][1])
        if best is None or best[0] > window_minutes * 60.0:
            return None
        return best[1]

    query = (
        "SELECT s.source, s.market_ticker, s.created_at, s.probability_yes,"
        " s.features, st.result_yes"
        " FROM signals s JOIN settlements st ON st.market_ticker = s.market_ticker"
        " WHERE s.source != 'market_prior'"
    )
    parameters: list[Any] = []
    if sources:
        placeholders = ",".join("?" for _ in sources)
        query += f" AND s.source IN ({placeholders})"
        parameters.extend(sources)
    from autonomy.taxonomy import grading_scope, horizon_bucket, market_type_for

    rows: list[MinedRow] = []
    for record in conn.execute(query, parameters):
        source, ticker, created_at, probability, features_json, result_yes = record
        stamp = _ts(created_at)
        market_probability = _nearest_prior(str(ticker), stamp) if stamp is not None else None
        if market_probability is None:
            continue
        try:
            features = json.loads(features_json or "{}")
        except json.JSONDecodeError:
            features = {}
        if not isinstance(features, dict):
            features = {}
        # Surface the grading-scope axes as features so mined rules can carry
        # horizon/market-type context (both point-in-time: horizon comes from
        # the persisted emission-time hours_to_close).
        features = {
            **features,
            "horizon_bucket": horizon_bucket(str(ticker), features.get("hours_to_close")),
            "market_type": features.get("market_type")
            or market_type_for(str(source), str(ticker), features),
        }
        rows.append(MinedRow(
            source=str(source),
            ticker=str(ticker),
            event_cluster=str(ticker).rsplit("-", 1)[0],
            created_at=str(created_at),
            probability_yes=float(probability),
            market_probability=float(market_probability),
            result_yes=bool(result_yes),
            features=features,
            scope=grading_scope(str(source), str(ticker), features),
        ))
    # Sort by PARSED time, not the raw string: ISO strings only sort
    # chronologically when every writer uses the same UTC offset format,
    # and the walk-forward split must never trust that.
    rows.sort(key=lambda row: _parse_ts(row.created_at) or 0.0)
    return rows


def _terciles(values: list[float]) -> list[float]:
    ordered = sorted(values)
    n = len(ordered)
    if n < 3:
        return []
    cuts = []
    for fraction in (1.0 / 3.0, 2.0 / 3.0):
        index = min(n - 1, max(0, int(round(fraction * (n - 1)))))
        cuts.append(ordered[index])
    return sorted(set(cuts))


def candidate_rules(train: list[MinedRow]) -> list[Rule]:
    """Bounded predicate space fit on TRAIN data only."""
    predicates: list[Predicate] = []
    for feature in NUMERIC_FEATURES:
        values = []
        for row in train:
            value = row.features.get(feature)
            if value is None:
                continue
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
        if len(values) < MIN_TRAIN_SAMPLES:
            continue
        for threshold in _terciles(values):
            predicates.append(Predicate(feature, "<=", threshold))
            predicates.append(Predicate(feature, ">", threshold))
    rules: list[Rule] = [Rule((predicate,)) for predicate in predicates]
    # Depth-2 conjunctions across DIFFERENT features, capped hard.
    for index, first in enumerate(predicates):
        for second in predicates[index + 1:]:
            if first.feature == second.feature:
                continue
            rules.append(Rule((first, second)))
            if len(rules) >= MAX_CANDIDATE_RULES:
                return rules
    return rules


def _purged_split(rows: list[MinedRow], train_fraction: float = 0.6) -> tuple[list[MinedRow], list[MinedRow]]:
    """Chronological split with event-cluster purging.

    Clusters straddling the boundary are dropped from TEST so no event can
    appear on both sides.
    """
    if not rows:
        return [], []
    cut = int(len(rows) * train_fraction)
    train = rows[:cut]
    train_clusters = {row.event_cluster for row in train}
    test = [row for row in rows[cut:] if row.event_cluster not in train_clusters]
    return train, test


def _cluster_mean_edges(rows: list[MinedRow]) -> list[float]:
    """One mean edge per event cluster.

    Emissions within a cluster share the same settlement print, so treating
    them as independent samples would shrink the CI dishonestly; the cluster
    mean is the honest unit of evidence.
    """
    sums: dict[str, list[float]] = {}
    for row in rows:
        sums.setdefault(row.event_cluster, []).append(_brier_edge(row))
    return [sum(edges) / len(edges) for edges in sums.values()]


def mine_rules(
    rows: list[MinedRow],
    *,
    min_train: int = MIN_TRAIN_SAMPLES,
    min_test: int = MIN_TEST_SAMPLES,
    min_test_clusters: int = MIN_TEST_CLUSTERS,
    top_k: int = 12,
) -> tuple[list[RuleEvidence], int]:
    """Walk-forward rule mining over settled, market-benchmarked rows.

    Returns (evidence, rules_tested) so callers can disclose the family
    size behind the per-rule confidence intervals.
    """
    train, test = _purged_split(rows)
    if len(train) < min_train or len(test) < min_test:
        return [], 0
    baseline_edges = _cluster_mean_edges(train)
    baseline_train = sum(baseline_edges) / len(baseline_edges)
    results: list[RuleEvidence] = []
    rules_tested = 0
    for rule in candidate_rules(train):
        train_hits = [row for row in train if rule.matches(row)]
        if len(train_hits) < min_train:
            continue
        train_cluster_edges = _cluster_mean_edges(train_hits)
        train_edge = sum(train_cluster_edges) / len(train_cluster_edges)
        # Only rules that OUTPERFORM the unconditional baseline in train
        # graduate to the out-of-sample exam.
        if train_edge <= max(0.0, baseline_train):
            continue
        test_hits = [row for row in test if rule.matches(row)]
        if len(test_hits) < min_test:
            continue
        edges = _cluster_mean_edges(test_hits)
        if len(edges) < min_test_clusters:
            continue
        rules_tested += 1
        stats = mean_ci95(edges) or {}
        mean = float(stats.get("mean") or 0.0)
        low = stats.get("lower")
        high = stats.get("upper")
        if low is None or high is None:
            continue  # no dispersion estimate -> no verdict either way
        verdict = "candidate" if float(low) > 0.0 else "rejected"
        low, high = float(low), float(high)
        results.append(RuleEvidence(
            rule=rule.describe(),
            n_train=len(train_hits),
            n_test=len(test_hits),
            train_edge=round(train_edge, 6),
            test_edge=round(mean, 6),
            test_ci95_low=round(low, 6),
            test_ci95_high=round(high, 6),
            verdict=verdict,
            detail={
                "sources": sorted({row.source for row in test_hits}),
                "test_clusters": len(edges),
                "test_win_rate": round(
                    sum(1 for row in test_hits if row.result_yes) / len(test_hits), 4,
                ),
            },
        ))
    results.sort(key=lambda evidence: (
        evidence.verdict != "candidate", -evidence.test_ci95_low,
    ))
    return results[:top_k], rules_tested


def mining_report(
    conn: sqlite3.Connection,
    *,
    sources: tuple[str, ...] | None = None,
    now_iso: str,
) -> dict[str, Any]:
    """One full mining pass -> JSON-able proposal artifact."""
    rows = load_settled_rows(conn, sources=sources)
    mined, rules_tested = mine_rules(rows)
    return {
        "generated_at": now_iso,
        "settled_rows": len(rows),
        "sources": sorted({row.source for row in rows}),
        "rules": [
            {
                "rule": evidence.rule,
                "n_train": evidence.n_train,
                "n_test": evidence.n_test,
                "train_brier_edge": evidence.train_edge,
                "test_brier_edge": evidence.test_edge,
                "test_ci95": [evidence.test_ci95_low, evidence.test_ci95_high],
                "verdict": evidence.verdict,
                **evidence.detail,
            }
            for evidence in mined
        ],
        "candidate_count": sum(1 for e in mined if e.verdict == "candidate"),
        # Multiple-testing disclosure: each rule is examined once at a
        # one-sided ~2.5% level, so this many false candidates are EXPECTED
        # from noise alone across the tested family. Candidates are leads
        # for the challenger pipeline, not validated edges.
        "rules_tested": rules_tested,
        "expected_false_positives": round(rules_tested * 0.025, 2),
        "note": (
            "Proposal artifact only. Rules are mined walk-forward from settled,"
            " market-benchmarked signal history (including setups never acted"
            " on); CIs use per-event-cluster means; adopting a rule is an"
            " explicit governance action and any adopted rule ships"
            " challenger-only first."
        ),
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
