"""Contraction-only or proposal-only homeostatic interventions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from dummy.constitution import Authority
from dummy.homeostasis.health_state import HealthLevel
from dummy.homeostasis.variables import HealthVariable
from dummy.world_model.models import digest_json


class Intervention(str, Enum):
    ABSTAIN = "abstain"
    CAP_FAMILY_WEIGHT = "cap_family_weight"
    INCREASE_MARKET_ANCHOR = "increase_market_anchor"
    PAUSE_MUTATION = "pause_mutation"
    QUARANTINE_COMPONENT = "quarantine_component"
    REDUCE_COMPUTE_BUDGET = "reduce_compute_budget"
    REDUCE_QUEUE_INTAKE = "reduce_queue_intake"
    REQUEST_EVIDENCE = "request_evidence"
    REQUEST_HUMAN_REVIEW = "request_human_review"
    REQUEST_SOURCE_REFRESH = "request_source_refresh"
    RUN_FAMILY_ABLATION = "run_family_ablation"
    SPAWN_INDEPENDENT_CHALLENGER = "spawn_independent_challenger"


AUTOMATIC_CONTRACTION_ACTIONS = frozenset(
    {
        Intervention.ABSTAIN,
        Intervention.CAP_FAMILY_WEIGHT,
        Intervention.INCREASE_MARKET_ANCHOR,
        Intervention.PAUSE_MUTATION,
        Intervention.QUARANTINE_COMPONENT,
        Intervention.REDUCE_COMPUTE_BUDGET,
        Intervention.REDUCE_QUEUE_INTAKE,
        Intervention.REQUEST_EVIDENCE,
        Intervention.REQUEST_SOURCE_REFRESH,
    }
)


@dataclass(frozen=True, slots=True)
class InterventionProposal:
    proposal_id: str
    state_id: str
    variable: HealthVariable
    level: HealthLevel
    interventions: tuple[Intervention, ...]
    evidence_ids: tuple[str, ...]
    authority_before: Authority
    authority_after: Authority
    automatic_eligible: bool
    applied: bool = False

    def __post_init__(self) -> None:
        interventions = tuple(sorted(self.interventions, key=lambda item: item.value))
        if not interventions or len(interventions) != len(set(interventions)):
            raise ValueError("intervention proposal requires unique actions")
        if self.authority_after > self.authority_before:
            raise ValueError("homeostatic intervention cannot expand authority")
        eligible = all(item in AUTOMATIC_CONTRACTION_ACTIONS for item in interventions)
        if self.automatic_eligible is not eligible:
            raise ValueError("automatic eligibility does not match contraction policy")
        if self.applied:
            raise ValueError("Phase 7 artifacts are proposal-only")
        object.__setattr__(self, "interventions", interventions)
        if self.proposal_id != digest_json(self.semantic_dict()):
            raise ValueError("intervention proposal ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "state_id": self.state_id,
            "variable": self.variable.value,
            "level": self.level.name,
            "interventions": [item.value for item in self.interventions],
            "evidence_ids": list(self.evidence_ids),
            "authority_before": self.authority_before.name,
            "authority_after": self.authority_after.name,
            "automatic_eligible": self.automatic_eligible,
            "applied": False,
            "authority_expansion": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"proposal_id": self.proposal_id, **self.semantic_dict()}


__all__ = [
    "AUTOMATIC_CONTRACTION_ACTIONS",
    "Intervention",
    "InterventionProposal",
]
