"""Aggregate-only private selection evaluator controlled outside candidates."""

from __future__ import annotations

from typing import Any

from dummy.world_model.models import digest_json

from .complexity_gate import (
    ComplexityBudget,
    evaluate_complexity,
)
from .metrics import compute_metrics
from .models import (
    ComplexityProfile,
    EvaluationPartition,
    EvaluationSummary,
    PrivateEvaluationReceipt,
    ResearchTask,
)
from .reward_hacking_detector import audit_reward_hacking


PRIVATE_EVALUATOR_VERSION = "dummy-autoresearch-private-v1"


def evaluate_private_selection(
    candidate_id: str,
    tasks: tuple[ResearchTask, ...],
    *,
    complexity_profile: ComplexityProfile = ComplexityProfile(),
    complexity_budget: ComplexityBudget = ComplexityBudget(),
) -> tuple[EvaluationSummary, PrivateEvaluationReceipt]:
    if not tasks or any(
        item.partition is not EvaluationPartition.PRIVATE_SELECTION for item in tasks
    ):
        raise ValueError("private evaluator accepts only private-selection tasks")
    complexity = evaluate_complexity(complexity_profile, complexity_budget)
    reward_audit = audit_reward_hacking(tasks)
    computation = compute_metrics(
        tasks,
        complexity=complexity,
        reward_audit=reward_audit,
    )
    interval = computation.confidence_interval
    gates = (
        (
            "verified_point_in_time_settlement",
            all(item.point_in_time_verified and item.settlement_verified for item in tasks),
        ),
        (
            "causal_close_bound_declared",
            all(
                item.close_time_provenance
                in {"EXACT_MARKET_CLOSE", "SETTLEMENT_RECEIPT_UPPER_BOUND"}
                for item in tasks
            ),
        ),
        (
            "realized_evidence_only",
            all(
                item.evidence_reality.upper()
                not in {"SYNTHETIC", "SIMULATED", "HYPOTHESIS"}
                for item in tasks
            ),
        ),
        ("no_forced_coverage_contamination", not any(item.forced_coverage for item in tasks)),
        ("reward_hacking_traps_clear", reward_audit.passed),
        (
            "private_calibration_not_worse",
            computation.candidate_calibration_error
            <= computation.incumbent_calibration_error + 0.01,
        ),
        (
            "compute_normalized_quality_not_worse",
            computation.candidate_compute_efficiency
            >= computation.incumbent_compute_efficiency,
        ),
        (
            "execution_truth_preserved",
            not any(
                item.candidate_claimed_fill_performance
                and not item.candidate_fill_verified
                for item in tasks
            ),
        ),
        ("deterministic_replay", all(item.replay_stable for item in tasks)),
        ("complexity_budget", complexity.passed),
        ("abstention_not_gamed", computation.abstention_rate <= 0.5),
        (
            "abstention_quality_nonnegative",
            computation.metrics.abstention_quality >= 0.0,
        ),
        ("contested_evidence_present", computation.contested_count > 0),
        (
            "cluster_interval_positive",
            interval is not None and interval[0] > 0.0,
        ),
        ("multi_objective_fitness_positive", computation.fitness > 0.0),
    )
    accepted = all(passed for _, passed in gates)
    summary = EvaluationSummary.create(
        candidate_id=candidate_id,
        partition=EvaluationPartition.PRIVATE_SELECTION,
        metrics=computation.metrics,
        fitness=computation.fitness,
        hard_gates=gates,
        accepted=accepted,
        task_count=len(tasks),
        event_cluster_count=len({item.event_cluster_id for item in tasks}),
        confidence_interval=interval,
        item_feedback=(),
        selection_eligible=True,
    )
    return summary, PrivateEvaluationReceipt.from_summary(summary)


def private_evaluator_manifest() -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": 1,
        "evaluator_version": PRIVATE_EVALUATOR_VERSION,
        "outer_loop_receives": [
            "aggregate_fitness",
            "accept_or_reject",
            "failed_gate_ids",
            "metric_digest",
            "coarse_evidence_count_buckets",
        ],
        "outer_loop_never_receives": [
            "case_ids",
            "dates",
            "teams_or_symbols",
            "strikes",
            "item_probabilities",
            "item_outcomes",
            "item_failures",
            "trap_identity_by_case",
        ],
        "hard_gates": [
            "future_leakage",
            "forced_coverage_contamination",
            "calibration_regression",
            "compute_only_gain",
            "execution_truth",
            "deterministic_replay",
            "reward_hacking",
            "complexity",
            "abstention_gaming",
            "cluster_robust_improvement",
        ],
        "candidate_controls_evaluator": False,
        "automatic_promotion": False,
        "execution_authority": False,
    }
    body["manifest_id"] = digest_json(body)
    return body


__all__ = [
    "PRIVATE_EVALUATOR_VERSION",
    "evaluate_private_selection",
    "private_evaluator_manifest",
]
