"""Fail-closed candidate lifecycle across public, private, and external gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dummy.world_model.models import digest_json

from .external_evaluator import evaluate_external_generalization
from .models import (
    ComplexityProfile,
    EvaluationPartition,
    EvaluationSummary,
    PrivateEvaluationReceipt,
    TaskSuite,
)
from .private_evaluator import evaluate_private_selection
from .public_evaluator import evaluate_visible_development


@dataclass(frozen=True, slots=True)
class CandidateLifecycleResult:
    lifecycle_id: str
    candidate_id: str
    constitution_allowed: bool
    public_evaluation: EvaluationSummary | None
    private_receipt: PrivateEvaluationReceipt | None
    external_evaluation: EvaluationSummary | None
    survived_private_selection: bool
    forward_paper_required: bool
    human_promotion_required: bool = True

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "candidate_id": self.candidate_id,
            "constitution_allowed": self.constitution_allowed,
            "public_evaluation_id": (
                self.public_evaluation.evaluation_id if self.public_evaluation else None
            ),
            "private_receipt": (
                self.private_receipt.to_dict() if self.private_receipt else None
            ),
            "external_evaluation_id": (
                self.external_evaluation.evaluation_id
                if self.external_evaluation
                else None
            ),
            "survived_private_selection": self.survived_private_selection,
            "forward_paper_required": self.forward_paper_required,
            "human_promotion_required": self.human_promotion_required,
            "source_edit_applied": False,
            "runtime_application": False,
            "automatic_promotion": False,
            "execution_authority": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"lifecycle_id": self.lifecycle_id, **self.semantic_dict()}


def run_candidate_lifecycle(
    candidate_id: str,
    suite: TaskSuite,
    *,
    constitution_allowed: bool,
    complexity_profile: ComplexityProfile = ComplexityProfile(),
) -> CandidateLifecycleResult:
    public: EvaluationSummary | None = None
    private_receipt: PrivateEvaluationReceipt | None = None
    external: EvaluationSummary | None = None
    survived = False
    forward_required = False
    if constitution_allowed:
        public = evaluate_visible_development(
            candidate_id,
            suite.partition(EvaluationPartition.VISIBLE_DEVELOPMENT),
            complexity_profile=complexity_profile,
        )
        if public.accepted:
            private, private_receipt = evaluate_private_selection(
                candidate_id,
                suite.partition(EvaluationPartition.PRIVATE_SELECTION),
                complexity_profile=complexity_profile,
            )
            survived = private.accepted
            if survived:
                external = evaluate_external_generalization(
                    candidate_id,
                    suite.partition(EvaluationPartition.EXTERNAL_GENERALIZATION),
                    complexity_profile=complexity_profile,
                )
                forward_required = external.accepted
    semantic = {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "constitution_allowed": constitution_allowed,
        "public_evaluation_id": public.evaluation_id if public else None,
        "private_receipt": private_receipt.to_dict() if private_receipt else None,
        "external_evaluation_id": external.evaluation_id if external else None,
        "survived_private_selection": survived,
        "forward_paper_required": forward_required,
        "human_promotion_required": True,
        "source_edit_applied": False,
        "runtime_application": False,
        "automatic_promotion": False,
        "execution_authority": False,
    }
    return CandidateLifecycleResult(
        lifecycle_id=digest_json(semantic),
        candidate_id=candidate_id,
        constitution_allowed=constitution_allowed,
        public_evaluation=public,
        private_receipt=private_receipt,
        external_evaluation=external,
        survived_private_selection=survived,
        forward_paper_required=forward_required,
    )


def lifecycle_manifest() -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": 1,
        "stages": [
            "parent_genome_selection",
            "outer_mutation_proposal",
            "static_constitutional_checks",
            "visible_replay_and_debugging",
            "private_hidden_evaluation",
            "cost_normalization",
            "reward_hacking_audit",
            "complexity_and_replay_audit",
            "selection_accept_or_reject",
            "external_generalization_observation",
            "forward_paper_shadow_deployment",
            "human_promotion_review",
        ],
        "external_can_change_selection": False,
        "forward_paper_required_after_private_survival": True,
        "human_promotion_required": True,
        "execution_authority": False,
    }
    body["manifest_id"] = digest_json(body)
    return body


__all__ = [
    "CandidateLifecycleResult",
    "lifecycle_manifest",
    "run_candidate_lifecycle",
]
