"""Intelligence-Lab campaign SWEEP at scale (Wave-4).

Wave-3 (``wave_streams``) runs one campaign over one cohort. Real research runs
over MANY cohorts at once -- every (stream x subject x market_type x phase) the
ledger carries -- which multiplies the multiple-comparisons surface: search 200
cohorts x 10 candidates and dozens of "edges" survive by chance alone. This
module runs the sweep honestly:

  * groups a stream's records into cohorts by ``cohort_scope`` (the same key the
    partition plan enforces), skipping -- and DISCLOSING -- cohorts too small to
    partition (fail-closed, never a silent drop),
  * scores each complexity-passing candidate on the cohort's VISIBLE partition
    only (no lookahead) against a paired-Brier statistic vs the market prior,
  * pools every (cohort, candidate) test and controls the portfolio false-
    discovery rate with Benjamini-Hochberg, so a reviewer sees BOTH the naive
    survivor count and the count that survives FDR correction, plus the total
    family searched.

Research/observation only: nothing here reaches execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, Callable, Iterable

from .complexity_gate import ComplexityBudget, evaluate_complexity
from .ledger_pipeline import LedgerEvidenceRow
from .models import AutoresearchValidationError, ComplexityProfile, EvaluationPartition
from .wave_streams import adapt_stream, build_stream_partition_plan

_NORMAL = NormalDist()
_MIN_SCORING_ROWS = 2  # need >= 2 visible clusters to form a variance estimate


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """A candidate rule the sweep can both gate on complexity AND score.

    ``predict`` maps one evidence row to the rule's P(yes); the sweep grades it
    against the settled ``result_yes`` on the visible partition.
    """

    rule_id: str
    description: str
    predict: Callable[[LedgerEvidenceRow], float]
    complexity: ComplexityProfile


@dataclass(frozen=True, slots=True)
class CohortTest:
    scope: str
    rule_id: str
    n: int
    brier_gain: float   # mean paired (prior_brier - candidate_brier); >0 = better
    p_value: float


@dataclass(frozen=True, slots=True)
class SweepResult:
    stream: str
    cohorts_evaluated: int
    cohorts_skipped: tuple[tuple[str, str], ...]        # (scope, reason)
    tests: tuple[CohortTest, ...]
    survivors_fdr: tuple[CohortTest, ...]
    family_size: int
    naive_significant: int
    fdr_q: float
    reaches_execution: bool = False

    def to_dict(self) -> dict[str, Any]:
        expected_fp = self.family_size * self.fdr_q
        return {
            "stream": self.stream,
            "cohorts_evaluated": self.cohorts_evaluated,
            "cohorts_skipped": [
                {"scope": scope, "reason": reason} for scope, reason in self.cohorts_skipped
            ],
            "family_size_searched": self.family_size,
            "naive_significant_at_q": self.naive_significant,
            "fdr_survivors": len(self.survivors_fdr),
            "fdr_q": self.fdr_q,
            "expected_false_positives_uncorrected": round(expected_fp, 4),
            "survivors": [
                {"scope": t.scope, "rule_id": t.rule_id, "n": t.n,
                 "brier_gain": round(t.brier_gain, 6), "p_value": round(t.p_value, 6)}
                for t in self.survivors_fdr
            ],
            "multiple_comparisons_note": (
                f"searched {self.family_size} (cohort x candidate) tests; naive "
                f"{self.naive_significant} significant at q={self.fdr_q}, but only "
                f"{len(self.survivors_fdr)} survive Benjamini-Hochberg FDR control -- "
                "the rest are consistent with multiple-comparisons noise"
            ),
            "reaches_execution": self.reaches_execution,
            "point_in_time_method": "visible_partition_only_no_lookahead",
        }


def cohorts_from_records(
    stream: str, records: Iterable[dict[str, Any]]
) -> dict[str, list[LedgerEvidenceRow]]:
    """Group a stream's records into evidence rows keyed by cohort_scope."""
    grouped: dict[str, list[LedgerEvidenceRow]] = {}
    for row in adapt_stream(stream, records):
        grouped.setdefault(row.cohort_scope, []).append(row)
    return grouped


def _paired_brier_test(
    candidate: ScoredCandidate, rows: tuple[LedgerEvidenceRow, ...]
) -> tuple[int, float, float] | None:
    """(n_clusters, mean_brier_gain, one_sided_p), or None if < 2 clusters.

    Gain = (prior - y)^2 - (p_candidate - y)^2; positive means the candidate
    beat the market prior. A one-sample z on the paired gains gives a one-sided
    p (H0: no gain).

    CRITICAL: the unit of independent evidence is the EVENT CLUSTER, not the row.
    One cluster (e.g. a 15m window) can carry many correlated strike rows; scoring
    them as independent understates variance and inflates significance -- so each
    cluster is first collapsed to its mean prediction / mean outcome / mean prior
    (the same one-unit-per-cluster convention as ``fit_reliability_map``), and the
    z-test runs over clusters. The partition plan already froze each cluster to a
    single date, so a cluster never spans partitions here.
    """
    # cluster_id -> [sum_p, sum_y, sum_prior, count]
    agg: dict[str, list[float]] = {}
    for row in rows:
        y = 1.0 if row.result_yes else 0.0
        p = min(1.0, max(0.0, float(candidate.predict(row))))
        acc = agg.setdefault(str(row.event_cluster_id), [0.0, 0.0, 0.0, 0.0])
        acc[0] += p
        acc[1] += y
        acc[2] += row.market_prior_probability
        acc[3] += 1.0
    gains: list[float] = []
    for sum_p, sum_y, sum_prior, count in agg.values():
        mean_p, mean_y, mean_prior = sum_p / count, sum_y / count, sum_prior / count
        gains.append((mean_prior - mean_y) ** 2 - (mean_p - mean_y) ** 2)
    n = len(gains)
    if n < _MIN_SCORING_ROWS:
        return None
    mean = sum(gains) / n
    var = sum((g - mean) ** 2 for g in gains) / (n - 1)
    if var <= 0.0:
        # Zero variance: significant iff a strictly positive constant gain.
        return n, mean, (0.0 if mean > 0.0 else 1.0)
    se = (var / n) ** 0.5
    z = mean / se
    return n, mean, 1.0 - _NORMAL.cdf(z)


def benjamini_hochberg(p_values: list[float], q: float) -> set[int]:
    """Indices rejected by Benjamini-Hochberg at FDR level ``q``."""
    if not p_values:
        return set()
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    threshold_rank = -1
    for rank, idx in enumerate(order, start=1):
        if p_values[idx] <= (rank / m) * q:
            threshold_rank = rank
    if threshold_rank < 0:
        return set()
    return {order[i] for i in range(threshold_rank)}


def run_campaign_sweep(
    stream: str,
    records: Iterable[dict[str, Any]],
    *,
    candidates: Iterable[ScoredCandidate],
    budget: ComplexityBudget = ComplexityBudget(),
    fdr_q: float = 0.10,
) -> SweepResult:
    """Sweep every cohort in one stream; FDR-control the pooled candidate tests."""
    candidate_list = list(candidates)
    passing = [c for c in candidate_list if evaluate_complexity(c.complexity, budget).passed]

    cohorts = cohorts_from_records(stream, records)
    tests: list[CohortTest] = []
    skipped: list[tuple[str, str]] = []
    evaluated = 0

    for scope, rows in sorted(cohorts.items()):
        try:
            plan = build_stream_partition_plan(rows, scope=scope)
        except AutoresearchValidationError as exc:
            skipped.append((scope, f"unpartitionable: {exc}"))
            continue
        visible_ids = {
            row_id for row_id, part in plan.assignments
            if part is EvaluationPartition.VISIBLE_DEVELOPMENT
        }
        visible = tuple(r for r in rows if r.evidence_row_id in visible_ids)
        if len(visible) < _MIN_SCORING_ROWS:
            skipped.append((scope, "too few visible rows to score"))
            continue
        evaluated += 1
        for candidate in passing:
            result = _paired_brier_test(candidate, visible)
            if result is None:
                continue
            n, gain, p = result
            tests.append(CohortTest(scope=scope, rule_id=candidate.rule_id,
                                    n=n, brier_gain=gain, p_value=p))

    family_size = len(passing) * evaluated  # the true test surface searched
    p_values = [t.p_value for t in tests]
    naive = sum(1 for p in p_values if p <= fdr_q)
    rejected = benjamini_hochberg(p_values, fdr_q)
    survivors = tuple(
        sorted((tests[i] for i in rejected), key=lambda t: t.p_value)
    )

    return SweepResult(
        stream=stream,
        cohorts_evaluated=evaluated,
        cohorts_skipped=tuple(skipped),
        tests=tuple(tests),
        survivors_fdr=survivors,
        family_size=family_size,
        naive_significant=naive,
        fdr_q=fdr_q,
    )
