"""Semantic distillation that retains only independently revalidated gains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from dummy.world_model.models import digest_json

from .complexity_gate import complexity_score
from .models import (
    AutoresearchValidationError,
    ComplexityProfile,
    EvaluationPartition,
    EvaluationSummary,
)


@dataclass(frozen=True, slots=True)
class MinimizationDecision:
    decision_id: str
    original_candidate_id: str
    minimized_candidate_id: str
    selected_candidate_id: str
    retained_minimized: bool
    reason: str
    behavioral_spec_digest: str
    source_edit_applied: bool = False

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "original_candidate_id": self.original_candidate_id,
            "minimized_candidate_id": self.minimized_candidate_id,
            "selected_candidate_id": self.selected_candidate_id,
            "retained_minimized": self.retained_minimized,
            "reason": self.reason,
            "behavioral_spec_digest": self.behavioral_spec_digest,
            "source_edit_applied": self.source_edit_applied,
            "automatic_promotion": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"decision_id": self.decision_id, **self.semantic_dict()}


def select_minimized_candidate(
    original: EvaluationSummary,
    minimized: EvaluationSummary,
    *,
    original_complexity: ComplexityProfile,
    minimized_complexity: ComplexityProfile,
    behavioral_spec: Mapping[str, Any],
    fitness_tolerance: float = 0.0025,
) -> MinimizationDecision:
    if (
        original.partition is not EvaluationPartition.PRIVATE_SELECTION
        or minimized.partition is not EvaluationPartition.PRIVATE_SELECTION
    ):
        raise AutoresearchValidationError("minimization requires private re-evaluation")
    if not behavioral_spec:
        raise AutoresearchValidationError(
            "minimization requires a machine-readable behavioral specification"
        )
    behavioral_spec_digest = digest_json(dict(behavioral_spec))
    original_score = complexity_score(original_complexity)
    minimized_score = complexity_score(minimized_complexity)
    retained = (
        original.accepted
        and minimized.accepted
        and minimized.fitness >= original.fitness - fitness_tolerance
        and minimized_score < original_score
    )
    if not minimized.accepted:
        reason = "minimized_candidate_failed_private_gate"
    elif minimized.fitness < original.fitness - fitness_tolerance:
        reason = "private_gain_was_fragile_under_simplification"
    elif minimized_score >= original_score:
        reason = "minimized_candidate_did_not_reduce_complexity"
    else:
        reason = "simpler_candidate_retained_private_gain"
    selected = minimized.candidate_id if retained else original.candidate_id
    semantic = {
        "schema_version": 1,
        "original_candidate_id": original.candidate_id,
        "minimized_candidate_id": minimized.candidate_id,
        "selected_candidate_id": selected,
        "retained_minimized": retained,
        "reason": reason,
        "behavioral_spec_digest": behavioral_spec_digest,
        "source_edit_applied": False,
        "automatic_promotion": False,
    }
    return MinimizationDecision(
        decision_id=digest_json(semantic),
        original_candidate_id=original.candidate_id,
        minimized_candidate_id=minimized.candidate_id,
        selected_candidate_id=selected,
        retained_minimized=retained,
        reason=reason,
        behavioral_spec_digest=behavioral_spec_digest,
    )


__all__ = ["MinimizationDecision", "select_minimized_candidate"]
