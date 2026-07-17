"""Wave-4: Intelligence-Lab campaign sweep at scale + FDR-controlled disclosure."""
from __future__ import annotations

import pytest

from dummy.autoresearch.campaign_sweep import (
    ScoredCandidate,
    benjamini_hochberg,
    cohorts_from_records,
    run_campaign_sweep,
    _paired_brier_test,
)
from dummy.autoresearch.models import ComplexityProfile
from dummy.autoresearch.wave_streams import clv_evidence_row


def _clv_record(day, *, subject, our_prob, prior=0.5):
    result = day % 2 == 0
    return {
        "decision_id": f"clv-{subject}-{day:02d}",
        "market_ticker": f"KXMLB-{day:02d}-{subject.upper()}",
        "event_cluster_id": f"{subject}-cluster-{day:02d}",
        "decision_at": f"2026-07-{day:02d}T18:00:00+00:00",
        "settlement_received_at": f"2026-07-{day:02d}T23:30:00+00:00",
        "our_probability": our_prob(result),
        "close_probability": prior,
        "result_yes": result,
        "subject": subject,
        "vertical": "sports",
        "market_type": "winner",
        "phase": "pre",
        "clv_bps": 10.0,
    }


def _predictive_records(subject, days):
    # our_probability tracks the outcome -> a candidate reading it beats the 0.5 prior.
    return [_clv_record(d, subject=subject, our_prob=lambda r: 0.9 if r else 0.1) for d in days]


def _null_records(subject, days):
    return [_clv_record(d, subject=subject, our_prob=lambda r: 0.5) for d in days]


_GOOD = ScoredCandidate("trust_incumbent", "use our forecast",
                        lambda row: row.incumbent_probability, ComplexityProfile(changed_modules=1))
_NULL = ScoredCandidate("copy_prior", "restate the market prior",
                        lambda row: row.market_prior_probability, ComplexityProfile(changed_modules=1))
_OVERCOMPLEX = ScoredCandidate("adds_dep", "adds a dependency",
                               lambda row: row.incumbent_probability, ComplexityProfile(added_dependencies=1))


def _row_in_cluster(cluster, idx, *, our_prob, prior=0.5, result=True):
    day = (idx % 27) + 1
    return clv_evidence_row({
        "decision_id": f"c-{cluster}-{idx}",
        "market_ticker": f"KXMLB-{cluster}-{idx}",
        "event_cluster_id": cluster,
        "decision_at": f"2026-07-{day:02d}T18:00:00+00:00",
        "settlement_received_at": f"2026-07-{day:02d}T23:30:00+00:00",
        "our_probability": our_prob,
        "close_probability": prior,
        "result_yes": result,
        "subject": "nyy",
        "vertical": "sports",
        "market_type": "winner",
        "phase": "pre",
    })


def test_paired_brier_scores_per_cluster_not_per_row():
    # ONE event cluster with 20 correlated strike rows must count as ONE unit of
    # evidence (n=1 -> None), never as 20 independent observations. This is the
    # fix for the inflated-significance bug: correlated rows sharing a cluster
    # cannot manufacture significance.
    rows = tuple(_row_in_cluster("clusterA", i, our_prob=0.9, result=True) for i in range(20))
    assert _paired_brier_test(_GOOD, rows) is None  # 20 rows, 1 cluster -> not enough

    # Two clusters (10 correlated rows each) collapse to n=2 clusters, not 20.
    two = tuple(
        _row_in_cluster("clusterA", i, our_prob=0.8, result=True) for i in range(10)
    ) + tuple(
        _row_in_cluster("clusterB", i, our_prob=0.2, result=False) for i in range(10)
    )
    result = _paired_brier_test(_GOOD, two)
    assert result is not None
    n, _gain, _p = result
    assert n == 2  # clusters, not the 20 rows


# ---- grouping ----------------------------------------------------------------

def test_cohorts_grouped_by_scope():
    records = _predictive_records("nyy", range(1, 6)) + _null_records("bos", range(1, 6))
    cohorts = cohorts_from_records("sports_clv", records)
    assert set(cohorts) == {"sports|nyy|winner|pre", "sports|bos|winner|pre"}
    assert len(cohorts["sports|nyy|winner|pre"]) == 5


# ---- paired-Brier statistic --------------------------------------------------

def test_paired_brier_rewards_a_better_forecast():
    rows = [
        clv_evidence_row(_clv_record(2, subject="nyy", our_prob=lambda r: 0.8)),   # True
        clv_evidence_row(_clv_record(3, subject="nyy", our_prob=lambda r: 0.2)),   # False
        clv_evidence_row(_clv_record(4, subject="nyy", our_prob=lambda r: 0.75)),  # True
    ]
    good = _paired_brier_test(_GOOD, tuple(rows))
    assert good is not None
    n, gain, p = good
    assert n == 3 and gain > 0 and 0.0 <= p < 0.5   # beats the 0.5 prior
    # A candidate that just copies the prior earns exactly zero gain.
    n2, gain2, p2 = _paired_brier_test(_NULL, tuple(rows))
    assert gain2 == pytest.approx(0.0) and p2 == pytest.approx(1.0)


def test_paired_brier_needs_two_rows():
    one = [clv_evidence_row(_clv_record(2, subject="nyy", our_prob=lambda r: 0.8))]
    assert _paired_brier_test(_GOOD, tuple(one)) is None


# ---- Benjamini-Hochberg ------------------------------------------------------

def test_benjamini_hochberg_controls_fdr():
    # Step-up: largest rank k with p_(k) <= (k/m)*q is rank 4 (0.041<=0.08),
    # so all four smallest are rejected; only 0.9 (>0.10) survives as null.
    ps = [0.001, 0.008, 0.039, 0.041, 0.9]
    rejected = benjamini_hochberg(ps, 0.10)
    assert rejected == {0, 1, 2, 3}
    # A case where nothing passes the line: all four below-rank thresholds fail.
    assert benjamini_hochberg([0.20, 0.30, 0.40, 0.50], 0.10) == set()
    assert benjamini_hochberg([0.5, 0.6, 0.7], 0.10) == set()
    assert benjamini_hochberg([], 0.10) == set()


# ---- full sweep --------------------------------------------------------------

def test_sweep_evaluates_cohorts_skips_small_and_fdr_controls():
    records = (
        _predictive_records("nyy", range(1, 13))   # big, informative cohort
        + _null_records("bos", range(1, 13))        # big, null cohort
        + _predictive_records("tor", [1, 2])        # too small to partition -> skipped
    )
    result = run_campaign_sweep(
        "sports_clv", records, candidates=[_GOOD, _NULL, _OVERCOMPLEX], fdr_q=0.10,
    )
    # Two big cohorts scored; the 2-date one skipped and disclosed with a reason.
    assert result.cohorts_evaluated == 2
    skipped_scopes = {s for s, _ in result.cohorts_skipped}
    assert "sports|tor|winner|pre" in skipped_scopes
    assert all(reason for _, reason in result.cohorts_skipped)   # every skip has a reason

    # Over-complex candidate gated out BEFORE the family is counted.
    assert result.family_size == 2 * 2   # 2 passing candidates x 2 evaluated cohorts

    # The informative cohort's good candidate survives FDR; the null does not.
    survivor_keys = {(t.scope, t.rule_id) for t in result.survivors_fdr}
    assert ("sports|nyy|winner|pre", "trust_incumbent") in survivor_keys
    assert not any(rule == "copy_prior" for _s, rule in survivor_keys)

    # FDR survivors are always a subset of the naive-significant count.
    assert len(result.survivors_fdr) <= result.naive_significant

    payload = result.to_dict()
    assert payload["reaches_execution"] is False
    assert payload["point_in_time_method"] == "visible_partition_only_no_lookahead"
    assert "Benjamini-Hochberg" in payload["multiple_comparisons_note"]
    assert payload["fdr_survivors"] == len(result.survivors_fdr)


def test_sweep_with_no_candidates_is_empty_but_valid():
    records = _predictive_records("nyy", range(1, 13))
    result = run_campaign_sweep("sports_clv", records, candidates=[])
    assert result.family_size == 0
    assert result.survivors_fdr == ()
    assert result.cohorts_evaluated == 1
