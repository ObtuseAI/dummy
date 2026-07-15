"""External generalization evaluator that can never select mutations."""

from __future__ import annotations

from .complexity_gate import ComplexityBudget, evaluate_complexity
from .metrics import compute_metrics
from .models import (
    ComplexityProfile,
    EvaluationPartition,
    EvaluationSummary,
    ResearchTask,
)
from .reward_hacking_detector import audit_reward_hacking


def evaluate_external_generalization(
    candidate_id: str,
    tasks: tuple[ResearchTask, ...],
    *,
    complexity_profile: ComplexityProfile = ComplexityProfile(),
    complexity_budget: ComplexityBudget = ComplexityBudget(),
) -> EvaluationSummary:
    if not tasks or any(
        item.partition is not EvaluationPartition.EXTERNAL_GENERALIZATION
        for item in tasks
    ):
        raise ValueError("external evaluator accepts only external tasks")
    complexity = evaluate_complexity(complexity_profile, complexity_budget)
    reward_audit = audit_reward_hacking(tasks)
    computation = compute_metrics(
        tasks,
        complexity=complexity,
        reward_audit=reward_audit,
    )
    gates = (
        ("point_in_time_settlement", all(item.point_in_time_verified and item.settlement_verified for item in tasks)),
        (
            "realized_evidence_only",
            all(
                item.evidence_reality.upper()
                not in {"SYNTHETIC", "SIMULATED", "HYPOTHESIS"}
                for item in tasks
            ),
        ),
        ("reward_hacking_traps_clear", reward_audit.passed),
        ("deterministic_replay", all(item.replay_stable for item in tasks)),
        ("cross_regime_transfer_positive", computation.metrics.cross_regime_transfer > 0.0),
    )
    return EvaluationSummary.create(
        candidate_id=candidate_id,
        partition=EvaluationPartition.EXTERNAL_GENERALIZATION,
        metrics=computation.metrics,
        fitness=computation.fitness,
        hard_gates=gates,
        accepted=all(passed for _, passed in gates),
        task_count=len(tasks),
        event_cluster_count=len({item.event_cluster_id for item in tasks}),
        confidence_interval=computation.confidence_interval,
        item_feedback=(),
        selection_eligible=False,
    )


__all__ = ["evaluate_external_generalization"]
