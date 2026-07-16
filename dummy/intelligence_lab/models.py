"""Content-addressed contracts for Dummy's intelligence research laboratory.

These records describe research.  They never carry execution, settlement, or
promotion authority.  IDs are derived from semantic content so the same claim
cannot silently acquire a new identity between replays.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from dummy.world_model.models import digest_json, freeze_json, thaw_json


class IntelligenceLabValidationError(ValueError):
    """A scientific-memory or cognitive-research contract is unsafe."""


class CognitiveOperator(str, Enum):
    ANALOGY = "analogy"
    INVERSION = "inversion"
    MORPHOLOGICAL_SEARCH = "morphological_search"
    CROSS_DOMAIN_TRANSFER = "cross_domain_transfer"
    CONSTRAINT_RELAXATION = "constraint_relaxation"
    CONSTRAINT_INVERSION = "constraint_inversion"
    RECOMBINATION = "recombination"
    COUNTERFACTUAL = "counterfactual_reasoning"
    FIRST_PRINCIPLES = "first_principles_reconstruction"
    ABSTRACTION = "abstraction"


class GraphKind(str, Enum):
    KNOWLEDGE = "knowledge"
    PROBLEM = "problem"
    HYPOTHESIS = "hypothesis"
    THEORY = "theory"
    FAILURE = "failure"
    CAPABILITY = "capability"
    UNKNOWN = "unknown"
    OPPORTUNITY = "opportunity"
    RESEARCH = "research"


class ResearchStatus(str, Enum):
    PROPOSED = "proposed"
    ACCUMULATING = "accumulating_evidence"
    REJECTED = "rejected"
    REPLICATED = "replicated"


class TheoryMaturity(str, Enum):
    REJECTED = "rejected"
    HYPOTHESIS = "hypothesis"
    PROVISIONAL_THEORY = "provisional_theory"
    GENERAL_LAW = "general_law"


def _text(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise IntelligenceLabValidationError(f"{name} is required")
    return normalized


def _unique(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    normalized = tuple(sorted(_text(item, name) for item in values))
    if len(normalized) != len(set(normalized)):
        raise IntelligenceLabValidationError(f"{name} contains duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class ScientificObservation:
    observation_id: str
    domain_id: str
    graph_kind: GraphKind
    statement: str
    observed_at: str
    confidence: float
    evidence_ids: tuple[str, ...]
    attributes: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.domain_id, "domain_id")
        _text(self.statement, "statement")
        _text(self.observed_at, "observed_at")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise IntelligenceLabValidationError("confidence must be in [0, 1]")
        object.__setattr__(self, "evidence_ids", _unique(self.evidence_ids, "evidence_ids"))
        object.__setattr__(self, "attributes", freeze_json(self.attributes))
        if self.observation_id != digest_json(self.semantic_dict()):
            raise IntelligenceLabValidationError("observation_id does not match content")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "domain_id": self.domain_id,
            "graph_kind": self.graph_kind.value,
            "statement": self.statement,
            "observed_at": self.observed_at,
            "confidence": self.confidence,
            "evidence_ids": list(self.evidence_ids),
            "attributes": thaw_json(self.attributes),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "observation_id": self.observation_id}

def make_observation(
    *,
    domain_id: str,
    graph_kind: GraphKind,
    statement: str,
    observed_at: str,
    confidence: float,
    evidence_ids: tuple[str, ...],
    attributes: Mapping[str, Any],
) -> ScientificObservation:
    semantic = {
        "schema_version": 1,
        "domain_id": domain_id.strip(),
        "graph_kind": graph_kind.value,
        "statement": statement.strip(),
        "observed_at": observed_at.strip(),
        "confidence": float(confidence),
        "evidence_ids": list(sorted(item.strip() for item in evidence_ids)),
        "attributes": thaw_json(freeze_json(attributes)),
    }
    return ScientificObservation(observation_id=digest_json(semantic), **{
        "domain_id": semantic["domain_id"],
        "graph_kind": graph_kind,
        "statement": semantic["statement"],
        "observed_at": semantic["observed_at"],
        "confidence": semantic["confidence"],
        "evidence_ids": tuple(semantic["evidence_ids"]),
        "attributes": semantic["attributes"],
    })


@dataclass(frozen=True, slots=True)
class ResearchOpportunity:
    opportunity_id: str
    domain_id: str
    question: str
    importance: float
    tractability: float
    novelty: float
    source_observation_ids: tuple[str, ...]
    missing_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.domain_id, "domain_id")
        _text(self.question, "question")
        for name in ("importance", "tractability", "novelty"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise IntelligenceLabValidationError(f"{name} must be in [0, 1]")
        object.__setattr__(self, "source_observation_ids", _unique(self.source_observation_ids, "source observations"))
        object.__setattr__(self, "missing_evidence", _unique(self.missing_evidence, "missing evidence"))
        if self.opportunity_id != digest_json(self.semantic_dict()):
            raise IntelligenceLabValidationError("opportunity_id does not match content")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "domain_id": self.domain_id,
            "question": self.question,
            "importance": self.importance,
            "tractability": self.tractability,
            "novelty": self.novelty,
            "source_observation_ids": list(self.source_observation_ids),
            "missing_evidence": list(self.missing_evidence),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "opportunity_id": self.opportunity_id}


def make_opportunity(**kwargs: Any) -> ResearchOpportunity:
    semantic = {
        "schema_version": 1,
        "domain_id": str(kwargs["domain_id"]).strip(),
        "question": str(kwargs["question"]).strip(),
        "importance": float(kwargs["importance"]),
        "tractability": float(kwargs["tractability"]),
        "novelty": float(kwargs["novelty"]),
        "source_observation_ids": list(sorted(kwargs["source_observation_ids"])),
        "missing_evidence": list(sorted(kwargs["missing_evidence"])),
    }
    return ResearchOpportunity(
        opportunity_id=digest_json(semantic),
        domain_id=semantic["domain_id"],
        question=semantic["question"],
        importance=semantic["importance"],
        tractability=semantic["tractability"],
        novelty=semantic["novelty"],
        source_observation_ids=tuple(semantic["source_observation_ids"]),
        missing_evidence=tuple(semantic["missing_evidence"]),
    )


@dataclass(frozen=True, slots=True)
class CognitiveHypothesis:
    hypothesis_id: str
    domain_id: str
    opportunity_id: str
    operator: CognitiveOperator
    claim: str
    prediction: str
    falsifier: str
    target_metrics: tuple[str, ...]
    status: ResearchStatus = ResearchStatus.PROPOSED

    def __post_init__(self) -> None:
        for value, name in ((self.domain_id, "domain_id"), (self.opportunity_id, "opportunity_id"), (self.claim, "claim"), (self.prediction, "prediction"), (self.falsifier, "falsifier")):
            _text(value, name)
        object.__setattr__(self, "target_metrics", _unique(self.target_metrics, "target metrics"))
        if not self.target_metrics:
            raise IntelligenceLabValidationError("target metrics are required")
        if self.hypothesis_id != digest_json(self.semantic_dict()):
            raise IntelligenceLabValidationError("hypothesis_id does not match content")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "domain_id": self.domain_id,
            "opportunity_id": self.opportunity_id,
            "operator": self.operator.value,
            "claim": self.claim,
            "prediction": self.prediction,
            "falsifier": self.falsifier,
            "target_metrics": list(self.target_metrics),
            "status": self.status.value,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "hypothesis_id": self.hypothesis_id}


def make_hypothesis(**kwargs: Any) -> CognitiveHypothesis:
    operator = kwargs["operator"]
    status = kwargs.get("status", ResearchStatus.PROPOSED)
    semantic = {
        "schema_version": 1,
        "domain_id": str(kwargs["domain_id"]).strip(),
        "opportunity_id": str(kwargs["opportunity_id"]).strip(),
        "operator": operator.value,
        "claim": str(kwargs["claim"]).strip(),
        "prediction": str(kwargs["prediction"]).strip(),
        "falsifier": str(kwargs["falsifier"]).strip(),
        "target_metrics": list(sorted(kwargs["target_metrics"])),
        "status": status.value,
    }
    return CognitiveHypothesis(
        hypothesis_id=digest_json(semantic),
        domain_id=semantic["domain_id"],
        opportunity_id=semantic["opportunity_id"],
        operator=operator,
        claim=semantic["claim"],
        prediction=semantic["prediction"],
        falsifier=semantic["falsifier"],
        target_metrics=tuple(semantic["target_metrics"]),
        status=status,
    )


@dataclass(frozen=True, slots=True)
class ExperimentProtocol:
    experiment_id: str
    hypothesis_id: str
    domain_id: str
    intervention: str
    control: str
    private_metrics: tuple[str, ...]
    required_partitions: tuple[str, ...]
    compute_budget: float
    replication_seed_count: int
    status: ResearchStatus = ResearchStatus.PROPOSED

    def __post_init__(self) -> None:
        for value, name in ((self.hypothesis_id, "hypothesis_id"), (self.domain_id, "domain_id"), (self.intervention, "intervention"), (self.control, "control")):
            _text(value, name)
        object.__setattr__(self, "private_metrics", _unique(self.private_metrics, "private metrics"))
        object.__setattr__(self, "required_partitions", _unique(self.required_partitions, "partitions"))
        if self.compute_budget <= 0 or not math.isfinite(self.compute_budget):
            raise IntelligenceLabValidationError("compute budget must be positive")
        if self.replication_seed_count < 2:
            raise IntelligenceLabValidationError("at least two replication seeds are required")
        if self.experiment_id != digest_json(self.semantic_dict()):
            raise IntelligenceLabValidationError("experiment_id does not match content")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "hypothesis_id": self.hypothesis_id,
            "domain_id": self.domain_id,
            "intervention": self.intervention,
            "control": self.control,
            "private_metrics": list(self.private_metrics),
            "required_partitions": list(self.required_partitions),
            "compute_budget": self.compute_budget,
            "replication_seed_count": self.replication_seed_count,
            "status": self.status.value,
            "candidate_controls_evaluator": False,
            "authority": "SIMULATE_MAXIMUM",
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "experiment_id": self.experiment_id}


def make_experiment(**kwargs: Any) -> ExperimentProtocol:
    status = kwargs.get("status", ResearchStatus.PROPOSED)
    semantic = {
        "schema_version": 1,
        "hypothesis_id": str(kwargs["hypothesis_id"]).strip(),
        "domain_id": str(kwargs["domain_id"]).strip(),
        "intervention": str(kwargs["intervention"]).strip(),
        "control": str(kwargs["control"]).strip(),
        "private_metrics": list(sorted(kwargs["private_metrics"])),
        "required_partitions": list(sorted(kwargs["required_partitions"])),
        "compute_budget": float(kwargs["compute_budget"]),
        "replication_seed_count": int(kwargs["replication_seed_count"]),
        "status": status.value,
        "candidate_controls_evaluator": False,
        "authority": "SIMULATE_MAXIMUM",
    }
    return ExperimentProtocol(
        experiment_id=digest_json(semantic),
        hypothesis_id=semantic["hypothesis_id"],
        domain_id=semantic["domain_id"],
        intervention=semantic["intervention"],
        control=semantic["control"],
        private_metrics=tuple(semantic["private_metrics"]),
        required_partitions=tuple(semantic["required_partitions"]),
        compute_budget=semantic["compute_budget"],
        replication_seed_count=semantic["replication_seed_count"],
        status=status,
    )


@dataclass(frozen=True, slots=True)
class ReplicationReceipt:
    receipt_id: str
    hypothesis_id: str
    domain_id: str
    independence_key: str
    effect_lower_bound: float
    calibration_noninferior: bool
    deterministic_replay: bool
    reward_hack_free: bool
    fixed_cost_noninferior: bool
    future_leakage_free: bool
    forced_coverage_free: bool
    source_correlation_free: bool
    execution_truth_noninferior: bool
    complexity_noninferior: bool

    def __post_init__(self) -> None:
        for value, name in ((self.hypothesis_id, "hypothesis_id"), (self.domain_id, "domain_id"), (self.independence_key, "independence_key")):
            _text(value, name)
        if not math.isfinite(self.effect_lower_bound):
            raise IntelligenceLabValidationError("effect lower bound must be finite")
        if self.receipt_id != digest_json(self.semantic_dict()):
            raise IntelligenceLabValidationError("receipt_id does not match content")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "hypothesis_id": self.hypothesis_id,
            "domain_id": self.domain_id,
            "independence_key": self.independence_key,
            "effect_lower_bound": self.effect_lower_bound,
            "calibration_noninferior": self.calibration_noninferior,
            "deterministic_replay": self.deterministic_replay,
            "reward_hack_free": self.reward_hack_free,
            "fixed_cost_noninferior": self.fixed_cost_noninferior,
            "future_leakage_free": self.future_leakage_free,
            "forced_coverage_free": self.forced_coverage_free,
            "source_correlation_free": self.source_correlation_free,
            "execution_truth_noninferior": self.execution_truth_noninferior,
            "complexity_noninferior": self.complexity_noninferior,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "receipt_id": self.receipt_id}


def make_replication_receipt(**kwargs: Any) -> ReplicationReceipt:
    semantic = {
        "schema_version": 1,
        "hypothesis_id": str(kwargs["hypothesis_id"]).strip(),
        "domain_id": str(kwargs["domain_id"]).strip(),
        "independence_key": str(kwargs["independence_key"]).strip(),
        "effect_lower_bound": float(kwargs["effect_lower_bound"]),
        "calibration_noninferior": bool(kwargs["calibration_noninferior"]),
        "deterministic_replay": bool(kwargs["deterministic_replay"]),
        "reward_hack_free": bool(kwargs["reward_hack_free"]),
        "fixed_cost_noninferior": bool(kwargs["fixed_cost_noninferior"]),
        "future_leakage_free": bool(kwargs["future_leakage_free"]),
        "forced_coverage_free": bool(kwargs["forced_coverage_free"]),
        "source_correlation_free": bool(kwargs["source_correlation_free"]),
        "execution_truth_noninferior": bool(kwargs["execution_truth_noninferior"]),
        "complexity_noninferior": bool(kwargs["complexity_noninferior"]),
    }
    return ReplicationReceipt(receipt_id=digest_json(semantic), **{key: semantic[key] for key in semantic if key != "schema_version"})


@dataclass(frozen=True, slots=True)
class CognitiveGenome:
    genome_id: str
    label: str
    generation: int
    parent_genome_ids: tuple[str, ...]
    reasoning_strategies: tuple[str, ...]
    research_methods: tuple[str, ...]
    creative_operators: tuple[CognitiveOperator, ...]
    evaluation_methods: tuple[str, ...]
    memory_policies: tuple[str, ...]
    agent_organization: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.label, "label")
        if self.generation < 0:
            raise IntelligenceLabValidationError("generation cannot be negative")
        for name in ("parent_genome_ids", "reasoning_strategies", "research_methods", "evaluation_methods", "memory_policies", "agent_organization"):
            object.__setattr__(self, name, _unique(getattr(self, name), name))
        operators = tuple(sorted(set(self.creative_operators), key=lambda item: item.value))
        object.__setattr__(self, "creative_operators", operators)
        if self.genome_id != digest_json(self.semantic_dict()):
            raise IntelligenceLabValidationError("genome_id does not match content")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "label": self.label,
            "generation": self.generation,
            "parent_genome_ids": list(self.parent_genome_ids),
            "reasoning_strategies": list(self.reasoning_strategies),
            "research_methods": list(self.research_methods),
            "creative_operators": [item.value for item in self.creative_operators],
            "evaluation_methods": list(self.evaluation_methods),
            "memory_policies": list(self.memory_policies),
            "agent_organization": list(self.agent_organization),
            "authority_genes": False,
            "truth_genes": False,
            "promotion_genes": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "genome_id": self.genome_id}


def make_cognitive_genome(**kwargs: Any) -> CognitiveGenome:
    operators = tuple(sorted(set(kwargs["creative_operators"]), key=lambda item: item.value))
    semantic = {
        "schema_version": 1,
        "label": str(kwargs["label"]).strip(),
        "generation": int(kwargs["generation"]),
        "parent_genome_ids": list(sorted(kwargs["parent_genome_ids"])),
        "reasoning_strategies": list(sorted(kwargs["reasoning_strategies"])),
        "research_methods": list(sorted(kwargs["research_methods"])),
        "creative_operators": [item.value for item in operators],
        "evaluation_methods": list(sorted(kwargs["evaluation_methods"])),
        "memory_policies": list(sorted(kwargs["memory_policies"])),
        "agent_organization": list(sorted(kwargs["agent_organization"])),
        "authority_genes": False,
        "truth_genes": False,
        "promotion_genes": False,
    }
    return CognitiveGenome(
        genome_id=digest_json(semantic),
        label=semantic["label"],
        generation=semantic["generation"],
        parent_genome_ids=tuple(semantic["parent_genome_ids"]),
        reasoning_strategies=tuple(semantic["reasoning_strategies"]),
        research_methods=tuple(semantic["research_methods"]),
        creative_operators=operators,
        evaluation_methods=tuple(semantic["evaluation_methods"]),
        memory_policies=tuple(semantic["memory_policies"]),
        agent_organization=tuple(semantic["agent_organization"]),
    )


__all__ = [
    "CognitiveGenome", "CognitiveHypothesis", "CognitiveOperator",
    "ExperimentProtocol", "GraphKind", "IntelligenceLabValidationError",
    "ReplicationReceipt", "ResearchOpportunity", "ResearchStatus",
    "ScientificObservation", "TheoryMaturity", "make_cognitive_genome",
    "make_experiment", "make_hypothesis", "make_observation",
    "make_opportunity", "make_replication_receipt",
]
