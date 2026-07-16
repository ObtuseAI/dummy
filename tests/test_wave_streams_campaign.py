"""Wave-3: Intelligence-Lab campaigns over Wave-1/2 instrumented evidence."""
from __future__ import annotations

import pytest

from dummy.autoresearch.models import (
    AutoresearchValidationError,
    ComplexityProfile,
    EvaluationPartition,
)
from dummy.autoresearch.wave_streams import (
    CampaignCandidate,
    adapt_stream,
    build_stream_partition_plan,
    clv_evidence_row,
    cross_venue_evidence_row,
    disclose_mined_family,
    fantasy_evidence_row,
    run_stream_campaign,
    tournament_cohort_evidence_row,
)

_SCOPE = "sports|nyy|winner|pre"


def _clv_record(day, *, cluster=None, subject="nyy", vertical="sports"):
    return {
        "decision_id": f"clv-{vertical}-{subject}-{day:02d}",
        "market_ticker": f"KXMLB-{day:02d}-NYY",
        "event_cluster_id": cluster or f"cluster-{day:02d}",
        "decision_at": f"2026-07-{day:02d}T18:00:00+00:00",
        "settlement_received_at": f"2026-07-{day:02d}T23:30:00+00:00",
        "our_probability": 0.61,
        "close_probability": 0.55,
        "result_yes": day % 2 == 0,
        "subject": subject,
        "vertical": vertical,
        "market_type": "winner",
        "phase": "pre",
        "clv_bps": 42.0,
    }


def _clv_rows(days):
    return adapt_stream("sports_clv", [_clv_record(d) for d in days])


# ---- adapters produce valid, point-in-time rows ------------------------------

def test_all_four_adapters_build_valid_rows():
    clv = clv_evidence_row(_clv_record(3))
    assert clv.vertical == "sports" and clv.source_family_ids == ("sports_clv",)
    assert clv.component_source == "sports_clv"

    tourn = tournament_cohort_evidence_row({
        "decision_id": "t1", "market_ticker": "KXMLB-01-NYY", "subject": "nyy",
        "decision_at": "2026-07-01T18:00:00+00:00",
        "settlement_received_at": "2026-07-01T23:00:00+00:00",
        "probability_yes": 0.6, "market_prior": 0.55, "result_yes": True,
        "cohort": "C2", "settled_pnl_cents": 130, "fill_count": 1, "price_cents": 47,
        "market_type": "winner",
    })
    assert tourn.source_family_ids == ("execution_tournament::C2",)
    assert tourn.settled_pnl_cents == 130

    fan = fantasy_evidence_row({
        "decision_id": "f1", "market_ticker": "KXMLB-01-NYY", "subject": "nyy",
        "decision_at": "2026-07-01T18:00:00+00:00",
        "settlement_received_at": "2026-07-01T23:00:00+00:00",
        "crowd_probability": 0.58, "market_prior": 0.55, "result_yes": False,
        "market_type": "winner", "ownership": 0.31,
    })
    assert fan.vertical == "mlb" and fan.component_source == "espn_fantasy_crowd"

    xv = cross_venue_evidence_row({
        "decision_id": "x1", "market_ticker": "KXBTCD-01-T70000", "subject": "btc",
        "decision_at": "2026-07-01T18:00:00+00:00",
        "settlement_received_at": "2026-07-01T23:00:00+00:00",
        "kalshi_probability": 0.4, "polymarket_probability": 0.47, "result_yes": True,
        "vertical": "crypto", "market_type": "threshold",
    })
    assert xv.source_family_ids == ("cross_venue_polymarket_crypto",)
    assert xv.component_probability == pytest.approx(0.47)


def test_content_addressing_is_deterministic():
    a = clv_evidence_row(_clv_record(5))
    b = clv_evidence_row(_clv_record(5))
    assert a.evidence_row_id == b.evidence_row_id


def test_point_in_time_violation_is_rejected():
    bad = _clv_record(4)
    bad["settlement_received_at"] = bad["decision_at"]  # settle not after decision
    with pytest.raises(AutoresearchValidationError):
        clv_evidence_row(bad)


# ---- partition plan enforces no-lookahead ------------------------------------

def test_partition_plan_splits_all_three_partitions():
    rows = _clv_rows(range(1, 13))  # 12 distinct dates
    plan = build_stream_partition_plan(rows, scope=_SCOPE)
    partitions = {p for _, p in plan.assignments}
    assert partitions == set(EvaluationPartition)
    manifest = plan.public_manifest()
    assert manifest["item_assignments_exposed"] is False
    assert sum(manifest["counts"].values()) == len(plan.assignments)


def test_partition_plan_rejects_mixed_cohorts():
    rows = _clv_rows([1, 2, 3]) + adapt_stream(
        "sports_clv", [_clv_record(4, subject="bos")]  # different subject -> other cohort
    )
    with pytest.raises(AutoresearchValidationError):
        build_stream_partition_plan(rows, scope=_SCOPE)


def test_late_cluster_observation_is_excluded_no_lookahead():
    # A single event cluster observed on an early AND a late date is frozen to
    # its earliest date; the later observation is dropped so a strike added
    # after the split cannot bridge partitions (structural no-lookahead).
    records = [_clv_record(d) for d in range(1, 13)]
    early = _clv_record(1, cluster="shared")
    late = _clv_record(12, cluster="shared")   # same cluster, later date
    records += [early, late]
    rows = adapt_stream("sports_clv", records)
    late_row = clv_evidence_row(late)
    plan = build_stream_partition_plan(rows, scope=_SCOPE)
    assert late_row.evidence_row_id in plan.excluded_late_cluster_observation_ids
    # The early observation of the cluster is still eligible (assigned).
    assigned_ids = {row_id for row_id, _ in plan.assignments}
    assert clv_evidence_row(early).evidence_row_id in assigned_ids


# ---- bounded campaign + complexity gate + honest disclosure ------------------

def _simple_candidate(rule_id):
    return CampaignCandidate(rule_id, "cheap rule", ComplexityProfile(changed_modules=1))


def _overcomplex_candidate(rule_id):
    # added_dependencies > 0 trips ComplexityBudget.max_added_dependencies == 0.
    return CampaignCandidate(rule_id, "adds a dependency", ComplexityProfile(added_dependencies=1))


def test_campaign_gates_complexity_and_discloses_family():
    records = [_clv_record(d) for d in range(1, 13)]
    candidates = [_simple_candidate("r1"), _simple_candidate("r2"), _overcomplex_candidate("r3")]
    result = run_stream_campaign(
        "sports_clv", records, scope=_SCOPE, candidates=candidates,
    )
    kept_ids = {c["rule_id"] for c in result["kept_candidates"]}
    assert kept_ids == {"r1", "r2"}                       # over-complex r3 gated out
    disc = result["mined_family_disclosure"]
    assert disc["family_size_searched"] == 3
    assert disc["complexity_passed"] == 2 and disc["kept"] == 2
    assert result["reaches_execution"] is False
    assert result["point_in_time_method"] == "visible_partition_only_no_lookahead"
    assert result["visible_evidence_rows"] >= 1


def test_disclosure_flags_multiple_comparisons_noise():
    # Searched 100, kept 3, alpha 0.05 -> expected 5 false positives >= kept.
    noisy = disclose_mined_family(family_size=100, complexity_passed=10, kept=3, alpha=0.05)
    assert "UNPROVEN" in noisy.warning
    assert noisy.expected_false_positives == pytest.approx(5.0)
    # Searched 10, kept 3 -> exceeds expected 0.5, still demands OOS confirmation.
    strong = disclose_mined_family(family_size=10, complexity_passed=5, kept=3)
    assert "out-of-sample" in strong.warning
    # No survivor.
    assert "nothing to report" in disclose_mined_family(
        family_size=8, complexity_passed=0, kept=0).warning


def test_disclosure_rejects_impossible_counts():
    with pytest.raises(ValueError):
        disclose_mined_family(family_size=5, complexity_passed=2, kept=3)  # kept > passed
    with pytest.raises(ValueError):
        disclose_mined_family(family_size=2, complexity_passed=5, kept=1)  # passed > family
