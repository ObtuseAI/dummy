"""Claim-specific evidence and review contracts for Phase 8."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from dummy.world_model.models import digest_json


class ClaimCode(str, Enum):
    ORGANISM_OUTPERFORMANCE = "claim_1_organism_outperformance"
    ABSTENTION_VALUE = "claim_2_abstention_value"
    RESOURCE_EFFICIENCY = "claim_3_resource_efficiency"
    WORLD_MODEL_TRANSFER = "claim_4_world_model_transfer"
    EVOLUTION_HELD_OUT_IMPROVEMENT = "claim_5_evolution_held_out_improvement"
    CONTESTED_CLUSTERED_PERFORMANCE = "claim_6_contested_clustered_performance"
    EXECUTION_TRUTH_SEPARATION = "claim_7_execution_truth_separation"
    GOVERNANCE_PRESERVATION = "claim_8_governance_preservation"


class EvidenceRequirement(str, Enum):
    ABSTENTION_COMPARATOR = "abstention_comparator"
    AUTHORITY_NONEXPANSION = "authority_nonexpansion"
    CALIBRATION = "calibration"
    CONTESTED_FILTER = "contested_filter"
    CREDENTIAL_ISOLATION = "credential_isolation"
    DETERMINISTIC_REPLAY = "deterministic_replay"
    EVENT_CLUSTER_UNCERTAINTY = "event_cluster_uncertainty"
    EXECUTION_REALISM = "execution_realism"
    FILL_TRUTH_SEPARATION = "fill_truth_separation"
    FORWARD_PAPER = "forward_paper"
    GOVERNANCE_TESTS = "governance_tests"
    MARKET_PRIOR_COMPARISON = "market_prior_comparison"
    MULTIPLE_TESTING_CORRECTION = "multiple_testing_correction"
    POINT_IN_TIME_HELD_OUT = "point_in_time_held_out"
    QUALITY_NONINFERIORITY = "quality_noninferiority"
    RESOURCE_COST = "resource_cost"
    TRANSFER = "transfer"


class EvidenceReality(str, Enum):
    EMPIRICAL = "EMPIRICAL"
    GOVERNANCE = "GOVERNANCE"
    MECHANICAL = "MECHANICAL"
    SYNTHETIC = "SYNTHETIC"


class ClaimVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    SUPPORTED_GOVERNANCE_ONLY = "SUPPORTED_GOVERNANCE_ONLY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class ClaimDefinition:
    code: ClaimCode
    statement: str
    requirements: tuple[EvidenceRequirement, ...]
    empirical: bool
    minimum_event_clusters: int

    def __post_init__(self) -> None:
        requirements = tuple(sorted(self.requirements, key=lambda item: item.value))
        if not self.statement.strip() or not requirements:
            raise ValueError("claim definition requires a statement and evidence")
        if self.empirical and self.minimum_event_clusters < 2:
            raise ValueError("empirical claims require multiple event clusters")
        if not self.empirical and self.minimum_event_clusters != 0:
            raise ValueError("governance claims do not use empirical cluster floors")
        object.__setattr__(self, "requirements", requirements)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "statement": self.statement,
            "requirements": [item.value for item in self.requirements],
            "empirical": self.empirical,
            "minimum_event_clusters": self.minimum_event_clusters,
        }


@dataclass(frozen=True, slots=True)
class ClaimEvidence:
    evidence_id: str
    requirement: EvidenceRequirement
    reality: EvidenceReality
    source_artifact: str
    assertion: str
    verified: bool
    point_in_time: bool
    held_out: bool
    observed_cases: int
    event_clusters: int
    candidate_controlled: bool = False
    issuer: str = "PROTECTED_EXTERNAL_AUDIT"

    def __post_init__(self) -> None:
        if not self.source_artifact.strip() or not self.assertion.strip():
            raise ValueError("claim evidence requires a source and assertion")
        if self.issuer != "PROTECTED_EXTERNAL_AUDIT" or self.candidate_controlled:
            raise ValueError("claim evidence must come from the protected external audit")
        if self.observed_cases < 0 or self.event_clusters < 0:
            raise ValueError("claim evidence counts must be non-negative")
        if self.event_clusters > self.observed_cases:
            raise ValueError("event cluster count cannot exceed observed cases")
        if self.reality is EvidenceReality.EMPIRICAL:
            if not self.point_in_time or not self.held_out or self.event_clusters == 0:
                raise ValueError("empirical evidence must be point-in-time held-out clusters")
        elif self.observed_cases or self.event_clusters:
            raise ValueError("non-empirical evidence cannot carry empirical case counts")
        if self.evidence_id != digest_json(self.semantic_dict()):
            raise ValueError("claim evidence ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "requirement": self.requirement.value,
            "reality": self.reality.value,
            "source_artifact": self.source_artifact,
            "assertion": self.assertion,
            "verified": self.verified,
            "point_in_time": self.point_in_time,
            "held_out": self.held_out,
            "observed_cases": self.observed_cases,
            "event_clusters": self.event_clusters,
            "candidate_controlled": False,
            "issuer": self.issuer,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"evidence_id": self.evidence_id, **self.semantic_dict()}


@dataclass(frozen=True, slots=True)
class ClaimReview:
    review_id: str
    definition: ClaimDefinition
    verdict: ClaimVerdict
    evidence_ids: tuple[str, ...]
    satisfied_requirements: tuple[EvidenceRequirement, ...]
    missing_requirements: tuple[EvidenceRequirement, ...]
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        evidence_ids = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        satisfied = tuple(sorted(self.satisfied_requirements, key=lambda item: item.value))
        missing = tuple(sorted(self.missing_requirements, key=lambda item: item.value))
        if set(satisfied) & set(missing) or set(satisfied) | set(missing) != set(
            self.definition.requirements
        ):
            raise ValueError("claim review requirements do not partition the definition")
        blockers = tuple(sorted(str(item).strip() for item in self.blockers))
        if self.verdict is ClaimVerdict.INSUFFICIENT_EVIDENCE and not blockers:
            raise ValueError("insufficient claim review requires blockers")
        if self.verdict in {ClaimVerdict.SUPPORTED, ClaimVerdict.SUPPORTED_GOVERNANCE_ONLY}:
            if missing or blockers:
                raise ValueError("supported claim review cannot have missing evidence")
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(self, "satisfied_requirements", satisfied)
        object.__setattr__(self, "missing_requirements", missing)
        object.__setattr__(self, "blockers", blockers)
        if self.review_id != digest_json(self.semantic_dict()):
            raise ValueError("claim review ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "definition": self.definition.to_dict(),
            "verdict": self.verdict.value,
            "evidence_ids": list(self.evidence_ids),
            "satisfied_requirements": [item.value for item in self.satisfied_requirements],
            "missing_requirements": [item.value for item in self.missing_requirements],
            "blockers": list(self.blockers),
            "automatic_promotion": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"review_id": self.review_id, **self.semantic_dict()}


__all__ = [
    "ClaimCode",
    "ClaimDefinition",
    "ClaimEvidence",
    "ClaimReview",
    "ClaimVerdict",
    "EvidenceReality",
    "EvidenceRequirement",
]
