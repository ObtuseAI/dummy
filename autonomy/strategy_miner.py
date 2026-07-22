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
    sample, a CI95 lower bound above zero, and a Benjamini-Hochberg discovery
    over the complete eligible out-of-sample family to be a candidate.
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
FDR_Q = 0.05
REPORT_TOP_K = 12


def _parse_ts(text: str) -> float | None:
    from datetime import datetime as _dt

    try:
        parsed = _dt.fromisoformat(str(text).replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.timestamp()
    except (OSError, OverflowError, ValueError):
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
    # Grading scope (source|subject|market_type|horizon_or_phase) so mined rules can
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
    one_sided_p_value: float
    fdr_q_value: float
    fdr_rejected_null: bool
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
    """Return canonical, forward-observed forecasts with a known prior.

    Evidence is deliberately stricter than a settlement join:

    * only live-observed rows are eligible (retro rows remain research-only);
    * source and receipt timestamps must be no later than the earliest
      decision, when one exists, otherwise settlement;
    * the benchmark is the latest already-received ``market_prior`` at or
      before the source emission -- a closer future prior is hindsight;
    * repeated emissions collapse to the latest valid row per
      source/contract/grading-horizon so cycle cadence cannot inflate ``n``.

    Missing or malformed provenance abstains. No replacement row is invented.
    """
    # Point-in-time prior matching is done in Python: the hot/archive union is
    # a connection-local view and receipt-time eligibility is clearer here
    # than in a correlated SQL subquery.
    import bisect
    import math

    from autonomy.retention import install_signal_history

    install_signal_history(conn)

    _ts = _parse_ts

    # Earliest decision is the evidence cutoff for a traded market. Any
    # malformed timestamp for that market quarantines it instead of silently
    # falling back to settlement.
    has_decisions = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='decisions'"
    ).fetchone() is not None
    decision_times: dict[str, float | None] = {}
    if has_decisions:
        for ticker, created_at in conn.execute(
            "SELECT market_ticker, created_at FROM decisions"
        ):
            key = str(ticker)
            stamp = _ts(str(created_at))
            if stamp is None:
                decision_times[key] = None
            elif key not in decision_times:
                decision_times[key] = stamp
            elif decision_times[key] is not None:
                decision_times[key] = min(float(decision_times[key]), stamp)

    # (created_ts, ingested_ts, id, probability). A retro or late-arriving
    # prior was not available to the source forecast even when its claimed
    # observation time is earlier.
    priors: dict[str, list[tuple[float, float, int, float]]] = {}
    for row_id, ticker, created_at, ingested_at, probability, mode in conn.execute(
        "SELECT id, market_ticker, created_at, ingested_at, probability_yes, mode"
        " FROM signal_history WHERE source = 'market_prior'",
    ):
        if str(mode).strip().lower() != "live":
            continue
        created_ts = _ts(created_at)
        ingested_ts = _ts(ingested_at)
        try:
            prior_probability = float(probability)
        except (TypeError, ValueError):
            continue
        if (
            created_ts is None
            or ingested_ts is None
            or ingested_ts < created_ts
            or not math.isfinite(prior_probability)
            or not 0.0 <= prior_probability <= 1.0
        ):
            continue
        priors.setdefault(str(ticker), []).append(
            (created_ts, ingested_ts, int(row_id), prior_probability)
        )
    for series in priors.values():
        series.sort()
    prior_stamps = {
        ticker: [entry[0] for entry in series]
        for ticker, series in priors.items()
    }

    def _latest_prior(
        ticker: str,
        signal_created_ts: float,
        signal_ingested_ts: float,
    ) -> float | None:
        series = priors.get(ticker)
        if not series:
            return None
        # Equal-time priors are eligible. Walk backward when the newest
        # claimed prior was received only after the source emission.
        index = bisect.bisect_right(
            prior_stamps[ticker], signal_created_ts,
        ) - 1
        while index >= 0:
            prior_created_ts, prior_ingested_ts, _row_id, probability = series[index]
            gap = signal_created_ts - prior_created_ts
            if gap > window_minutes * 60.0:
                return None
            if prior_ingested_ts <= signal_ingested_ts:
                return probability
            index -= 1
        return None

    query = (
        "SELECT s.id, s.source, s.market_ticker, s.created_at, s.ingested_at,"
        " s.probability_yes, s.features, s.mode, st.result_yes, st.settled_at"
        " FROM signal_history s JOIN settlements st ON st.market_ticker = s.market_ticker"
        " WHERE s.source != 'market_prior' AND LOWER(s.mode) = 'live'"
    )
    parameters: list[Any] = []
    if sources:
        placeholders = ",".join("?" for _ in sources)
        query += f" AND s.source IN ({placeholders})"
        parameters.extend(sources)
    from autonomy.taxonomy import grading_scope, horizon_bucket, market_type_for

    # key -> ((created_ts, ingested_ts, row_id), row). The scope contains the
    # horizon/phase axis, yielding one canonical source-contract-horizon row.
    canonical: dict[
        tuple[str, str, str],
        tuple[tuple[float, float, int], MinedRow],
    ] = {}
    for record in conn.execute(query, parameters):
        (
            row_id,
            source,
            ticker,
            created_at,
            ingested_at,
            probability,
            features_json,
            mode,
            result_yes,
            settled_at,
        ) = record
        if str(mode).strip().lower() != "live":
            continue
        created_ts = _ts(created_at)
        ingested_ts = _ts(ingested_at)
        settled_ts = _ts(settled_at)
        if created_ts is None or ingested_ts is None or settled_ts is None:
            continue
        if ingested_ts < created_ts:
            continue
        cutoff_ts = settled_ts
        if str(ticker) in decision_times:
            decision_ts = decision_times[str(ticker)]
            if decision_ts is None:
                continue
            cutoff_ts = min(cutoff_ts, decision_ts)
        if created_ts > cutoff_ts or ingested_ts > cutoff_ts:
            continue
        market_probability = _latest_prior(
            str(ticker), created_ts, ingested_ts,
        )
        if market_probability is None:
            continue
        try:
            source_probability = float(probability)
            outcome = float(result_yes)
        except (TypeError, ValueError):
            continue
        if (
            not math.isfinite(source_probability)
            or not 0.0 <= source_probability <= 1.0
            or not math.isfinite(outcome)
            or outcome not in (0.0, 1.0)
        ):
            continue
        # Wave-5 quarantine: drop pre-gate history whose recorded prior bears
        # the fabricated-mid signature (dead crypto ladder books). Post-gate
        # emissions can never form this pair (junk books emit no prior).
        from autonomy.quote_quality import suspect_crypto_contested_pair

        if suspect_crypto_contested_pair(
            source_probability, float(market_probability), str(ticker), str(created_at),
        ):
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
        scope = grading_scope(str(source), str(ticker), features)
        row = MinedRow(
            source=str(source),
            ticker=str(ticker),
            event_cluster=str(ticker).rsplit("-", 1)[0],
            created_at=str(created_at),
            probability_yes=source_probability,
            market_probability=float(market_probability),
            result_yes=bool(outcome),
            features=features,
            scope=scope,
        )
        key = (str(source), str(ticker), scope)
        rank = (created_ts, ingested_ts, int(row_id))
        held = canonical.get(key)
        if held is None or rank > held[0]:
            canonical[key] = (rank, row)
    rows = [entry[1] for entry in canonical.values()]
    # Sort by PARSED time, not the raw string: ISO strings only sort
    # chronologically when every writer uses the same UTC offset format,
    # and the walk-forward split must never trust that.
    rows.sort(key=lambda row: (
        _parse_ts(row.created_at) or 0.0,
        row.ticker,
        row.source,
        row.scope,
    ))
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


def _one_sided_cluster_sign_p_value(edges: list[float]) -> tuple[float, int, int]:
    """Exact distribution-free test that the median cluster edge is positive.

    The independent unit is one event-cluster mean, never an emission. Under
    ``H0: P(cluster_edge > 0) <= 0.5`` the positive-sign count is dominated by
    ``Binomial(n, 0.5)``. Zero edges are ties and are removed before the exact
    upper-tail calculation. This deliberately avoids turning the miner's
    approximate normal CI into a p-value.

    Returns ``(p_value, positive_clusters, nonzero_clusters)``.
    """
    nonzero = [float(edge) for edge in edges if abs(float(edge)) > 1e-15]
    n = len(nonzero)
    if n == 0:
        return 1.0, 0, 0
    positives = sum(edge > 0.0 for edge in nonzero)
    numerator = sum(math.comb(n, count) for count in range(positives, n + 1))
    p_value = float(numerator / (1 << n))
    if p_value == 0.0:
        p_value = math.ulp(0.0)
    return min(1.0, p_value), positives, n


def _benjamini_hochberg(
    p_values: list[float], *, q: float = FDR_Q,
) -> list[dict[str, Any]]:
    """Return deterministic Benjamini-Hochberg step-up decisions."""
    if not 0.0 < float(q) < 1.0:
        raise ValueError("FDR q must be in (0, 1)")
    parsed = [float(value) for value in p_values]
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in parsed):
        raise ValueError("p-values must be finite and in [0, 1]")
    family_size = len(parsed)
    if family_size == 0:
        return []
    ordered = sorted(enumerate(parsed), key=lambda item: (item[1], item[0]))
    reject_through_rank = 0
    for rank, (_index, p_value) in enumerate(ordered, start=1):
        if p_value <= float(q) * rank / family_size:
            reject_through_rank = rank
    adjusted_by_index = [1.0] * family_size
    rank_by_index = [0] * family_size
    running_adjusted = 1.0
    for position in range(family_size - 1, -1, -1):
        rank = position + 1
        index, p_value = ordered[position]
        running_adjusted = min(
            running_adjusted,
            min(1.0, p_value * family_size / rank),
        )
        adjusted_by_index[index] = running_adjusted
        rank_by_index[index] = rank
    return [
        {
            "rank": rank_by_index[index],
            "adjusted_q_value": adjusted_by_index[index],
            "rejected_null": rank_by_index[index] <= reject_through_rank,
        }
        for index in range(family_size)
    ]


def mine_rules(
    rows: list[MinedRow],
    *,
    min_train: int = MIN_TRAIN_SAMPLES,
    min_test: int = MIN_TEST_SAMPLES,
    min_test_clusters: int = MIN_TEST_CLUSTERS,
    top_k: int = 12,
) -> tuple[list[RuleEvidence], int]:
    """Walk-forward rule mining over settled, market-benchmarked rows.

    Thresholds and the train-performance screen use TRAIN only. Every rule
    that has outcome-independent sample support in TEST enters one FDR family;
    its verdict is assigned only after all out-of-sample p-values are known.

    Returns ``(evidence, rules_tested)`` where ``rules_tested`` is exactly the
    number of valid out-of-sample hypotheses in the BH family.
    """
    train, test = _purged_split(rows)
    if len(train) < min_train or len(test) < min_test:
        return [], 0
    baseline_edges = _cluster_mean_edges(train)
    baseline_train = sum(baseline_edges) / len(baseline_edges)
    results: list[RuleEvidence] = []
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
        stats = mean_ci95(edges) or {}
        mean = float(stats.get("mean") or 0.0)
        low = stats.get("lower")
        high = stats.get("upper")
        if low is None or high is None:
            continue  # no dispersion estimate -> no verdict either way
        low, high = float(low), float(high)
        p_value, positive_clusters, nonzero_clusters = (
            _one_sided_cluster_sign_p_value(edges)
        )
        results.append(RuleEvidence(
            rule=rule.describe(),
            n_train=len(train_hits),
            n_test=len(test_hits),
            train_edge=round(train_edge, 6),
            test_edge=round(mean, 6),
            test_ci95_low=round(low, 6),
            test_ci95_high=round(high, 6),
            one_sided_p_value=p_value,
            fdr_q_value=1.0,
            fdr_rejected_null=False,
            verdict="rejected",
            detail={
                "sources": sorted({row.source for row in test_hits}),
                "test_clusters": len(edges),
                "positive_nonzero_test_clusters": positive_clusters,
                "nonzero_test_clusters": nonzero_clusters,
                "test_win_rate": round(
                    sum(1 for row in test_hits if row.result_yes) / len(test_hits), 4,
                ),
            },
        ))
    rules_tested = len(results)
    fdr_decisions = _benjamini_hochberg(
        [evidence.one_sided_p_value for evidence in results], q=FDR_Q,
    )
    for evidence, decision in zip(results, fdr_decisions, strict=True):
        evidence.fdr_q_value = float(decision["adjusted_q_value"])
        evidence.fdr_rejected_null = bool(decision["rejected_null"])
        if evidence.fdr_rejected_null and evidence.test_ci95_low > 0.0:
            evidence.verdict = "candidate"
        evidence.detail.update({
            "one_sided_p_value": evidence.one_sided_p_value,
            "fdr_q_value": evidence.fdr_q_value,
            "fdr_rank": int(decision["rank"]),
            "fdr_rejected_null": evidence.fdr_rejected_null,
            "p_value_method": "exact_one_sided_event_cluster_sign_test",
        })
    results.sort(key=lambda evidence: (
        evidence.verdict != "candidate",
        evidence.fdr_q_value,
        -evidence.test_ci95_low,
        evidence.rule,
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
    all_mined, rules_tested = mine_rules(rows, top_k=MAX_CANDIDATE_RULES)
    mined = all_mined[:REPORT_TOP_K]
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
                "one_sided_p_value": evidence.one_sided_p_value,
                "fdr_q_value": evidence.fdr_q_value,
                "fdr_rejected_null": evidence.fdr_rejected_null,
                "verdict": evidence.verdict,
                **evidence.detail,
            }
            for evidence in mined
        ],
        "candidate_count": sum(
            1 for evidence in all_mined if evidence.verdict == "candidate"
        ),
        "rules_tested": rules_tested,
        "multiple_testing": {
            "method": "benjamini_hochberg",
            "target_fdr_q": FDR_Q,
            "family_size": rules_tested,
            "discoveries": sum(
                1 for evidence in all_mined if evidence.fdr_rejected_null
            ),
            "hypothesis": "median event-cluster Brier edge <= 0",
            "p_value_method": "exact_one_sided_event_cluster_sign_test",
            "dependency_assumption": (
                "positive regression dependence among overlapping fixed rules"
            ),
            "test_fold_role": "out_of_sample_verdict_only",
            "intervals_are_unadjusted_diagnostics": True,
            "candidate_requires": [
                "BH rejected null at target q",
                "unadjusted event-cluster mean CI95 lower bound > 0",
            ],
        },
        "note": (
            "Proposal artifact only. Rules are mined walk-forward from settled,"
            " market-benchmarked signal history (including setups never acted"
            " on); thresholds and screening use train only, while all verdicts"
            " use the later purged test fold; exact event-cluster sign p-values"
            " are Benjamini-Hochberg controlled across the complete eligible"
            " family. Adopting a rule is an explicit governance action and any"
            " adopted rule ships challenger-only first."
        ),
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
