"""Versioned, proposal-only genome mutations bounded by the constitution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Any, Mapping

from dummy.constitution import Authority, evaluate_mutation_proposal
from dummy.world_model.models import digest_json, freeze_json, thaw_json

from .schema import ForecastGenome, Gene, GeneCategory, GenomeValidationError


class MutationLevel(IntEnum):
    PARAMETERS = 0
    FEATURES = 1
    FORECAST_STRATEGY = 2
    AGENT_ORGANISM = 3
    METACOGNITIVE_CONTROL = 4
    MUTATION_SELECTION_POLICY = 5


class MutationOperator(str, Enum):
    ADD = "ADD"
    SET = "SET"
    REMOVE = "REMOVE"


LEVEL_CATEGORIES = {
    MutationLevel.PARAMETERS: frozenset(
        {
            GeneCategory.MARKET_PRIOR_WEIGHT,
            GeneCategory.REPLAY_DEPTH,
            GeneCategory.SIMULATION_BUDGET,
            GeneCategory.ABSTENTION_THRESHOLD,
        }
    ),
    MutationLevel.FEATURES: frozenset(
        {GeneCategory.FEATURE_SET, GeneCategory.SOURCE_SELECTION}
    ),
    MutationLevel.FORECAST_STRATEGY: frozenset(
        {
            GeneCategory.FORECAST_COMBINATION,
            GeneCategory.UNCERTAINTY_MODEL,
            GeneCategory.DECISION_RULE,
            GeneCategory.CALIBRATION_POLICY,
        }
    ),
    MutationLevel.AGENT_ORGANISM: frozenset(
        {GeneCategory.AGENT_COMPOSITION, GeneCategory.ADVERSARIAL_SEQUENCE}
    ),
    MutationLevel.METACOGNITIVE_CONTROL: frozenset(
        {GeneCategory.METACOGNITIVE_POLICY}
    ),
    MutationLevel.MUTATION_SELECTION_POLICY: frozenset(
        {GeneCategory.MUTATION_POLICY}
    ),
}


def _utc(value: datetime | str) -> datetime:
    parsed = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GenomeValidationError("mutation timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class MutationOperation:
    operator: MutationOperator
    gene_name: str
    category: GeneCategory
    value: Any
    gene_version: str
    rationale: str

    def __post_init__(self) -> None:
        if not self.gene_name.strip() or not self.rationale.strip():
            raise GenomeValidationError("mutation operation identity is required")
        if self.operator is not MutationOperator.REMOVE and not self.gene_version.strip():
            raise GenomeValidationError("mutation gene version is required")
        if self.operator is MutationOperator.REMOVE and self.value is not None:
            raise GenomeValidationError("REMOVE mutation cannot carry a value")
        object.__setattr__(self, "value", freeze_json(self.value))

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator.value,
            "gene_name": self.gene_name,
            "category": self.category.value,
            "value": thaw_json(self.value),
            "gene_version": self.gene_version,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MutationOperation:
        return cls(
            operator=MutationOperator(str(data["operator"])),
            gene_name=str(data["gene_name"]),
            category=GeneCategory(str(data["category"])),
            value=data.get("value"),
            gene_version=str(data.get("gene_version", "")),
            rationale=str(data["rationale"]),
        )


@dataclass(frozen=True, slots=True)
class GenomeMutationProposal:
    proposal_id: str
    base_genome_id: str
    level: MutationLevel
    operations: tuple[MutationOperation, ...]
    target_paths: tuple[str, ...]
    created_at: datetime
    evidence_ids: tuple[str, ...]
    allowed_by_constitution: bool
    blocked_paths: tuple[str, ...]
    guard_reasons: tuple[str, ...]
    candidate_genome: ForecastGenome | None

    def __post_init__(self) -> None:
        operations = tuple(
            sorted(self.operations, key=lambda item: (item.gene_name, item.operator.value))
        )
        if not operations or len({item.gene_name for item in operations}) != len(operations):
            raise GenomeValidationError("mutation operations must be non-empty and unique")
        allowed_categories = LEVEL_CATEGORIES[self.level]
        if any(item.category not in allowed_categories for item in operations):
            raise GenomeValidationError("mutation operation exceeds its recursive level")
        paths = tuple(sorted(str(item).strip() for item in self.target_paths))
        evidence = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        if any(not item for item in (*paths, *evidence)) or not paths or not evidence:
            raise GenomeValidationError("mutation paths and evidence are required")
        decision = evaluate_mutation_proposal(
            paths,
            proposer_authority=Authority.RECOMMEND,
        )
        if (
            self.allowed_by_constitution != decision.allowed
            or tuple(self.blocked_paths) != decision.blocked_paths
            or tuple(self.guard_reasons) != decision.reasons
        ):
            raise GenomeValidationError("mutation guard decision was not reproducible")
        if decision.allowed is not (self.candidate_genome is not None):
            raise GenomeValidationError("blocked mutation cannot materialize a candidate")
        created = _utc(self.created_at)
        object.__setattr__(self, "operations", operations)
        object.__setattr__(self, "target_paths", paths)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "created_at", created)
        if self.proposal_id != digest_json(self.semantic_dict()):
            raise GenomeValidationError("mutation proposal ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "base_genome_id": self.base_genome_id,
            "level": int(self.level),
            "operations": [item.to_dict() for item in self.operations],
            "target_paths": list(self.target_paths),
            "created_at": _iso(self.created_at),
            "evidence_ids": list(self.evidence_ids),
            "allowed_by_constitution": self.allowed_by_constitution,
            "blocked_paths": list(self.blocked_paths),
            "guard_reasons": list(self.guard_reasons),
            "candidate_genome": (
                self.candidate_genome.to_dict() if self.candidate_genome else None
            ),
            "applied": False,
            "automatic_promotion": False,
            "execution_authority": False,
            "promotion_authority": "HUMAN_ONLY",
        }

    def to_dict(self) -> dict[str, Any]:
        return {"proposal_id": self.proposal_id, **self.semantic_dict()}


def _candidate(
    base: ForecastGenome,
    *,
    operations: tuple[MutationOperation, ...],
    created_at: datetime,
    evidence_ids: tuple[str, ...],
) -> ForecastGenome:
    genes = {item.name: item for item in base.genes}
    for operation in operations:
        exists = operation.gene_name in genes
        if operation.operator is MutationOperator.ADD and exists:
            raise GenomeValidationError("ADD mutation targets an existing gene")
        if operation.operator in {MutationOperator.SET, MutationOperator.REMOVE} and not exists:
            raise GenomeValidationError(
                f"{operation.operator.value} mutation targets a missing gene"
            )
        if operation.operator is MutationOperator.REMOVE:
            del genes[operation.gene_name]
        else:
            genes[operation.gene_name] = Gene(
                name=operation.gene_name,
                category=operation.category,
                value=thaw_json(operation.value),
                version=operation.gene_version,
                evidence_ids=evidence_ids,
            )
    if not genes:
        raise GenomeValidationError("mutation cannot remove every gene")
    return ForecastGenome.create(
        label=f"{base.label} mutation",
        vertical=base.vertical,
        market_type=base.market_type,
        horizon=base.horizon,
        generation=base.generation + 1,
        parent_genome_ids=(base.genome_id,),
        genes=tuple(genes.values()),
        created_at=created_at,
        evidence_ids=tuple(sorted({base.genome_id, *base.evidence_ids, *evidence_ids})),
    )


def propose_mutation(
    base: ForecastGenome,
    *,
    level: MutationLevel,
    operations: tuple[MutationOperation, ...],
    target_paths: tuple[str, ...],
    created_at: datetime,
    evidence_ids: tuple[str, ...],
) -> GenomeMutationProposal:
    decision = evaluate_mutation_proposal(
        target_paths,
        proposer_authority=Authority.RECOMMEND,
    )
    candidate = (
        _candidate(
            base,
            operations=operations,
            created_at=created_at,
            evidence_ids=evidence_ids,
        )
        if decision.allowed
        else None
    )
    semantic = {
        "schema_version": 1,
        "base_genome_id": base.genome_id,
        "level": int(level),
        "operations": [
            item.to_dict()
            for item in sorted(
                operations,
                key=lambda item: (item.gene_name, item.operator.value),
            )
        ],
        "target_paths": sorted(target_paths),
        "created_at": _iso(created_at),
        "evidence_ids": sorted(evidence_ids),
        "allowed_by_constitution": decision.allowed,
        "blocked_paths": list(decision.blocked_paths),
        "guard_reasons": list(decision.reasons),
        "candidate_genome": candidate.to_dict() if candidate else None,
        "applied": False,
        "automatic_promotion": False,
        "execution_authority": False,
        "promotion_authority": "HUMAN_ONLY",
    }
    return GenomeMutationProposal(
        proposal_id=digest_json(semantic),
        base_genome_id=base.genome_id,
        level=level,
        operations=operations,
        target_paths=target_paths,
        created_at=created_at,
        evidence_ids=evidence_ids,
        allowed_by_constitution=decision.allowed,
        blocked_paths=decision.blocked_paths,
        guard_reasons=decision.reasons,
        candidate_genome=candidate,
    )


__all__ = [
    "GenomeMutationProposal",
    "MutationLevel",
    "MutationOperation",
    "MutationOperator",
    "propose_mutation",
]
