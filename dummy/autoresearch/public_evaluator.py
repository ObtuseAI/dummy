"""Visible development evaluator with item-level debugging feedback."""

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


def evaluate_visible_development(
    candidate_id: str,
    tasks: tuple[ResearchTask, ...],
    *,
    complexity_profile: ComplexityProfile = ComplexityProfile(),
    complexity_budget: ComplexityBudget = ComplexityBudget(),
) -> EvaluationSummary:
    if not tasks or any(
        item.partition is not EvaluationPartition.VISIBLE_DEVELOPMENT for item in tasks
    ):
        raise ValueError("public evaluator accepts only visible-development tasks")
    complexity = evaluate_complexity(complexity_profile, complexity_budget)
    reward_audit = audit_reward_hacking(tasks)
    computation = compute_metrics(
        tasks,
        complexity=complexity,
        reward_audit=reward_audit,
    )
    gates = (
        ("mechanical_replay", all(item.replay_stable for item in tasks)),
        ("visible_reward_hacking_traps_clear", reward_audit.passed),
        ("complexity_budget", complexity.passed),
    )
    feedback = tuple(
        {
            "case_id": item.case_id,
            "event_cluster_id": item.event_cluster_id,
            "candidate_abstained": item.candidate_abstained,
            "candidate_brier": (
                None
                if item.candidate_probability is None
                else (float(item.candidate_probability) - item.outcome) ** 2
            ),
            "incumbent_brier": (item.incumbent_probability - item.outcome) ** 2,
        }
        for item in tasks
    )
    return EvaluationSummary.create(
        candidate_id=candidate_id,
        partition=EvaluationPartition.VISIBLE_DEVELOPMENT,
        metrics=computation.metrics,
        fitness=computation.fitness,
        hard_gates=gates,
        accepted=all(passed for _, passed in gates),
        task_count=len(tasks),
        event_cluster_count=len({item.event_cluster_id for item in tasks}),
        confidence_interval=computation.confidence_interval,
        item_feedback=feedback,
        selection_eligible=False,
    )


__all__ = ["evaluate_visible_development"]
