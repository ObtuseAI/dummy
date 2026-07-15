"""Proposal-only outer researcher for improving forecast research organisms."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from dummy.genome import (
    ForecastGenome,
    GenomeMutationProposal,
    MutationLevel,
    MutationOperation,
    propose_mutation,
)
from dummy.world_model.models import digest_json

from .lineage_bandit import LineageAllocation, LineageState, allocate_lineage
from .models import (
    AutoresearchValidationError,
    PrivateEvaluationReceipt,
    ResearchPolicy,
)


@dataclass(frozen=True, slots=True)
class ResearchBudget:
    maximum_experiments: int
    maximum_compute_units: float
    maximum_cost_microunits: float
    maximum_wall_seconds: int

    def __post_init__(self) -> None:
        if (
            self.maximum_experiments < 1
            or self.maximum_compute_units <= 0
            or self.maximum_cost_microunits <= 0
            or self.maximum_wall_seconds < 1
        ):
            raise AutoresearchValidationError("research budget must be positive")

    def to_dict(self) -> dict[str, int | float]:
        return {
            "maximum_experiments": self.maximum_experiments,
            "maximum_compute_units": self.maximum_compute_units,
            "maximum_cost_microunits": self.maximum_cost_microunits,
            "maximum_wall_seconds": self.maximum_wall_seconds,
        }


@dataclass(frozen=True, slots=True)
class ResearchExperiment:
    experiment_id: str
    policy_id: str
    allocation: LineageAllocation
    mutation_proposal: GenomeMutationProposal
    budget: ResearchBudget
    source_edit_applied: bool = False
    runtime_application: bool = False

    def __post_init__(self) -> None:
        if self.source_edit_applied or self.runtime_application:
            raise AutoresearchValidationError(
                "outer researcher cannot apply source or runtime changes"
            )
        if self.experiment_id != digest_json(self.semantic_dict()):
            raise AutoresearchValidationError("research experiment ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "policy_id": self.policy_id,
            "allocation": self.allocation.to_dict(),
            "mutation_proposal_id": self.mutation_proposal.proposal_id,
            "candidate_genome_id": (
                self.mutation_proposal.candidate_genome.genome_id
                if self.mutation_proposal.candidate_genome
                else None
            ),
            "budget": self.budget.to_dict(),
            "source_edit_applied": self.source_edit_applied,
            "runtime_application": self.runtime_application,
            "private_item_access": False,
            "automatic_promotion": False,
            "execution_authority": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"experiment_id": self.experiment_id, **self.semantic_dict()}


class OuterEvolutionResearcher:
    """Select arms and propose typed mutations without hidden-task access."""

    def __init__(self, policy: ResearchPolicy) -> None:
        self.policy = policy

    def propose_experiment(
        self,
        *,
        lineage_states: tuple[LineageState, ...],
        base_genome: ForecastGenome,
        level: MutationLevel,
        operations: tuple[MutationOperation, ...],
        target_paths: tuple[str, ...],
        created_at: datetime,
        evidence_ids: tuple[str, ...],
        budget: ResearchBudget,
    ) -> ResearchExperiment:
        allowed_lineages = set(self.policy.lineage_ids)
        if not lineage_states or any(
            item.lineage_id not in allowed_lineages for item in lineage_states
        ):
            raise AutoresearchValidationError(
                "outer researcher received an undeclared lineage"
            )
        allocation = allocate_lineage(lineage_states)
        selected_parent = allocation.selected_parent_candidate_id
        if selected_parent is not None and selected_parent != base_genome.genome_id:
            raise AutoresearchValidationError(
                "base genome does not match greedy parent in selected lineage"
            )
        proposal = propose_mutation(
            base_genome,
            level=level,
            operations=operations,
            target_paths=target_paths,
            created_at=created_at,
            evidence_ids=evidence_ids,
        )
        semantic = {
            "schema_version": 1,
            "policy_id": self.policy.policy_id,
            "allocation": allocation.to_dict(),
            "mutation_proposal_id": proposal.proposal_id,
            "candidate_genome_id": (
                proposal.candidate_genome.genome_id
                if proposal.candidate_genome
                else None
            ),
            "budget": budget.to_dict(),
            "source_edit_applied": False,
            "runtime_application": False,
            "private_item_access": False,
            "automatic_promotion": False,
            "execution_authority": False,
        }
        return ResearchExperiment(
            experiment_id=digest_json(semantic),
            policy_id=self.policy.policy_id,
            allocation=allocation,
            mutation_proposal=proposal,
            budget=budget,
        )

    @staticmethod
    def ingest_private_receipt(
        lineage: LineageState,
        receipt: PrivateEvaluationReceipt,
    ) -> LineageState:
        """Update an arm from aggregate feedback; item data is not accepted."""

        scores = dict(lineage.candidate_scores)
        scores[receipt.candidate_id] = receipt.fitness
        return replace(
            lineage,
            private_rewards=(*lineage.private_rewards, receipt.fitness),
            candidate_scores=tuple(sorted(scores.items())),
            champion_candidate_id=max(scores.items(), key=lambda item: (item[1], item[0]))[0],
        )


def outer_researcher_manifest() -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": 1,
        "improved_object": "INNER_FORECAST_RESEARCH_ORGANISM",
        "improver": "OUTER_EVOLUTION_RESEARCHER",
        "outer_may_improve": [
            "agent_composition",
            "feature_selection",
            "context_construction",
            "challenger_search",
            "simulation_allocation",
            "source_family_weighting",
            "uncertainty_models",
            "abstention_logic",
            "adversarial_sequencing",
            "mutation_selection_policy",
        ],
        "outer_may_never_control": [
            "execution",
            "risk_limits",
            "credentials",
            "settlement_truth",
            "fill_truth",
            "private_evaluator",
            "external_evaluator",
            "promotion_law",
            "quarantine_release",
            "capital",
        ],
        "source_edits_applied": False,
        "runtime_application": False,
        "promotion_authority": "HUMAN_ONLY",
        "execution_authority": False,
    }
    body["manifest_id"] = digest_json(body)
    return body


__all__ = [
    "OuterEvolutionResearcher",
    "ResearchBudget",
    "ResearchExperiment",
    "outer_researcher_manifest",
]
