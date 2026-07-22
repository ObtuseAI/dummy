from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.backtest import LIVE_SOURCE_EVIDENCE_MODE
from autonomy.canary import evaluate_canary_readiness
from autonomy.capability_matrix import (
    build_live_source_capability_matrix,
    build_research_capability_matrix,
)
from autonomy.ledger import AutonomyLedger
from autonomy.simulation_training import execution_curriculum
from autonomy.taxonomy import grading_scope


def _execution_rows(count: int = 120, *, validation_fails: bool = False) -> list[dict]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        submitted = start + timedelta(hours=6 * index)
        pnl = -20 if validation_fails and 72 <= index < 96 else 50
        rows.append({
            "decision_id": f"execution-{index}",
            "ticker": f"EXEC-EVENT{index}-CONTRACT",
            "cluster": f"event-{index}",
            "price_cents": 20,
            "ev_cents": 10.0,
            "uncertainty": 0.1,
            "submitted_at": submitted.isoformat(),
            "queue_ahead": 0.0,
            "filled": True,
            "known": True,
            "known_at": (submitted + timedelta(minutes=30)).isoformat(),
            "fill_at": (submitted + timedelta(minutes=30)).isoformat(),
            "settled_at": (submitted + timedelta(hours=1)).isoformat(),
            "settled_pnl_cents": pnl,
        })
    return rows


def test_execution_experiment_closes_only_after_disjoint_holdout_passes():
    report = execution_curriculum(_execution_rows())
    experiment = report["experiment"]

    assert report["status"] == "SHADOW_EXPERIMENT_ELIGIBLE"
    assert report["eligible_for_shadow_experiment"] is True
    assert experiment["lifecycle_state"] == (
        "CLOSED_PASSED_SHADOW_REVIEW_ELIGIBLE"
    )
    assert experiment["candidate_state"] == "SHADOW_CHALLENGER_ONLY"
    assert experiment["closed"] is True
    assert experiment["holdout_evaluated"] is True
    assert experiment["evidence_separation"]["verified"] is True
    assert experiment["evidence_separation"]["cluster_intersections"] == {
        "training_validation": 0,
        "training_holdout": 0,
        "validation_holdout": 0,
    }
    assert experiment["execution_authority"] is False
    assert experiment["capital_authority"] is False
    assert report["auto_apply"] is False


def test_weak_execution_candidate_is_retired_before_holdout_is_opened():
    report = execution_curriculum(_execution_rows(validation_fails=True))
    experiment = report["experiment"]

    assert report["eligible_for_shadow_experiment"] is False
    assert report["status"] == "RETIRED"
    assert experiment["lifecycle_state"] == "CLOSED_RETIRED_VALIDATION_FAILURE"
    assert experiment["candidate_state"] == "RETIRED"
    assert experiment["closed"] is True
    assert experiment["holdout_evaluated"] is False
    assert experiment["holdout_result"] is None


def _live_capability_fixture(*, include_weight: bool = True, negative: bool = False):
    signals: dict[str, list[dict]] = {}
    for index in range(25):
        ticker = f"MTEST-EVENT{index}-CONTRACT"
        signals[ticker] = [
            {"source": "sharp", "features": {}},
            {
                "source": "new_idea",
                "features": {"challenger_only": True},
            },
        ]
    sharp_scope = grading_scope("sharp", "MTEST-EVENT0-CONTRACT", {})
    challenger_scope = grading_scope(
        "new_idea", "MTEST-EVENT0-CONTRACT", {"challenger_only": True},
    )
    sources = {
        sharp_scope: {
            "n": 25,
            "contested_n": 25,
            "contested_event_clusters": 25,
            "contested_mean_brier_edge_ci95": {
                "lower": -0.02 if negative else 0.01,
                "upper": -0.01 if negative else 0.08,
            },
        },
        challenger_scope: {
            "n": 2,
            "contested_n": 1,
            "contested_event_clusters": 1,
            "contested_mean_brier_edge_ci95": None,
        },
    }
    weights = {f"scope:{sharp_scope}": 1.3} if include_weight else {}
    return signals, sources, weights, sharp_scope, challenger_scope


def test_live_capability_requires_earned_exact_scope_but_not_challenger_sample():
    signals, sources, weights, sharp_scope, challenger_scope = (
        _live_capability_fixture()
    )
    matrix = build_live_source_capability_matrix(
        signals,
        sources,
        weights,
        source_evidence_mode=LIVE_SOURCE_EVIDENCE_MODE,
        required_evidence_mode=LIVE_SOURCE_EVIDENCE_MODE,
    )

    assert matrix["ready_for_live_canary"] is True
    assert matrix["shadow_collection_allowed"] is True
    assert matrix["challenger_grading_allowed"] is True
    assert matrix["scopes"][sharp_scope]["requires_live_capability_proof"] is True
    assert matrix["scopes"][challenger_scope][
        "requires_live_capability_proof"
    ] is False
    assert matrix["execution_authority"] is False


def test_live_capability_blocks_missing_weight_and_inline_negative_scope():
    signals, sources, _weights, sharp_scope, _challenger_scope = (
        _live_capability_fixture(include_weight=False)
    )
    missing = build_live_source_capability_matrix(
        signals,
        sources,
        {},
        source_evidence_mode=LIVE_SOURCE_EVIDENCE_MODE,
        required_evidence_mode=LIVE_SOURCE_EVIDENCE_MODE,
    )
    assert missing["ready_for_live_canary"] is False
    assert "earned_exact_scope_weight_missing" in missing["scopes"][sharp_scope][
        "blocking_reasons"
    ]

    signals, sources, weights, sharp_scope, _challenger_scope = (
        _live_capability_fixture(negative=True)
    )
    negative = build_live_source_capability_matrix(
        signals,
        sources,
        weights,
        source_evidence_mode=LIVE_SOURCE_EVIDENCE_MODE,
        required_evidence_mode=LIVE_SOURCE_EVIDENCE_MODE,
    )
    assert negative["ready_for_live_canary"] is False
    assert "decisively_negative_contested_brier_edge" in negative["scopes"][
        sharp_scope
    ]["blocking_reasons"]
    assert "no no-edge artifact dependency" in negative[
        "inline_negative_scope_check"
    ]


def test_canary_fails_closed_when_capability_matrix_is_missing(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        result = evaluate_canary_readiness(
            ledger,
            min_settled=0,
            min_policy_settled=0,
            min_canary_graded=0,
            backtest_report={
                "settled_markets": 0,
                "source_evidence_mode": LIVE_SOURCE_EVIDENCE_MODE,
                "sources": {},
                "execution_quality_by_book": {
                    "shadow": {"orders_with_confirmed_fill": 5},
                },
                "realized_trade_statistics": {},
                "fill_conditioned_decision_policy": {},
            },
        )
        assert result.ready is False
        assert "live source capability matrix is missing" in result.blockers
    finally:
        ledger.close()


def test_research_capability_matrix_reports_closure_without_authority():
    execution = execution_curriculum(_execution_rows())
    matrix = build_research_capability_matrix(
        forecast={"eligible_for_shadow_experiment": False},
        execution=execution,
        evolution={"population": {"candidates_generated": 4}},
    )

    assert matrix["overall_status"] == "EVIDENCE_DISCIPLINED_RESEARCH_ONLY"
    assert matrix["capabilities"]["experiment_closure"]["implemented"] is True
    assert matrix["capabilities"]["positive_promotion"]["implemented"] is False
    assert matrix["shadow_collection_allowed"] is True
    assert matrix["promotion_authority"] is False
    assert matrix["execution_authority"] is False
    assert matrix["capital_authority"] is False
