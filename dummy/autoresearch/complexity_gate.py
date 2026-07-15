"""Maintainability pressure and Pareto comparison for research mutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dummy.world_model.models import digest_json

from .models import ComplexityProfile


@dataclass(frozen=True, slots=True)
class ComplexityBudget:
    max_weighted_score: float = 20.0
    max_changed_modules: int = 8
    max_cyclomatic_delta: int = 12
    max_added_dependencies: int = 0
    max_new_artifact_schemas: int = 1
    max_replay_cost_delta: float = 0.25
    dead_code_allowed: int = 0


@dataclass(frozen=True, slots=True)
class ComplexityDecision:
    score: float
    passed: bool
    failed_gates: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 12),
            "passed": self.passed,
            "failed_gates": list(self.failed_gates),
        }


def complexity_score(profile: ComplexityProfile) -> float:
    return round(
        profile.changed_modules
        + 0.5 * profile.cyclomatic_delta
        + 0.5 * profile.new_branches
        + 0.25 * profile.new_configuration_values
        + 0.25 * profile.state_space_growth
        + 5.0 * profile.added_dependencies
        + 3.0 * profile.new_artifact_schemas
        + 10.0 * profile.replay_cost_delta
        + 0.25 * profile.explanation_complexity
        + 10.0 * profile.dead_code_items
        + 0.1 * profile.test_surface_expansion,
        12,
    )


def evaluate_complexity(
    profile: ComplexityProfile,
    budget: ComplexityBudget = ComplexityBudget(),
) -> ComplexityDecision:
    score = complexity_score(profile)
    checks = {
        "weighted_score": score <= budget.max_weighted_score,
        "changed_modules": profile.changed_modules <= budget.max_changed_modules,
        "cyclomatic_delta": profile.cyclomatic_delta <= budget.max_cyclomatic_delta,
        "added_dependencies": profile.added_dependencies <= budget.max_added_dependencies,
        "new_artifact_schemas": (
            profile.new_artifact_schemas <= budget.max_new_artifact_schemas
        ),
        "replay_cost_delta": profile.replay_cost_delta <= budget.max_replay_cost_delta,
        "dead_code": profile.dead_code_items <= budget.dead_code_allowed,
    }
    failed = tuple(name for name, passed in checks.items() if not passed)
    return ComplexityDecision(score=score, passed=not failed, failed_gates=failed)


def pareto_dominates(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> bool:
    """Compare (forecast fitness, resource cost, complexity), higher/lower/lower."""

    no_worse = left[0] >= right[0] and left[1] <= right[1] and left[2] <= right[2]
    strictly_better = left[0] > right[0] or left[1] < right[1] or left[2] < right[2]
    return no_worse and strictly_better


def complexity_policy_manifest() -> dict[str, Any]:
    budget = ComplexityBudget()
    body: dict[str, Any] = {
        "schema_version": 1,
        "budget": {
            field: getattr(budget, field) for field in budget.__dataclass_fields__
        },
        "fitness_frontier": ["forecast_fitness", "resource_cost", "complexity"],
        "dead_code_hard_gate": True,
        "semantic_distillation_required": True,
        "candidate_controls_gate": False,
    }
    body["manifest_id"] = digest_json(body)
    return body


__all__ = [
    "ComplexityBudget",
    "ComplexityDecision",
    "complexity_policy_manifest",
    "complexity_score",
    "evaluate_complexity",
    "pareto_dominates",
]
