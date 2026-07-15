"""Content-addressed forecast genome contracts for DUMMY vNext."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from dummy import VNEXT_MATURITY
from dummy.world_model.models import digest_json, freeze_json, thaw_json


_GENE_NAME = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")


class GenomeValidationError(ValueError):
    """A genome, lineage, mutation, or fitness record is invalid."""


class GeneCategory(str, Enum):
    AGENT_COMPOSITION = "agent_composition"
    SOURCE_SELECTION = "source_selection"
    FEATURE_SET = "feature_set"
    FORECAST_COMBINATION = "forecast_combination"
    MARKET_PRIOR_WEIGHT = "market_prior_weight"
    UNCERTAINTY_MODEL = "uncertainty_model"
    ADVERSARIAL_SEQUENCE = "adversarial_sequence"
    REPLAY_DEPTH = "replay_depth"
    SIMULATION_BUDGET = "simulation_budget"
    ABSTENTION_THRESHOLD = "abstention_threshold"
    DECISION_RULE = "decision_rule"
    CALIBRATION_POLICY = "calibration_policy"
    METACOGNITIVE_POLICY = "metacognitive_policy"
    MUTATION_POLICY = "mutation_policy"


class GenomeStatus(str, Enum):
    EXPERIMENTAL = "EXPERIMENTAL"
    QUARANTINED = "QUARANTINED"
    SHADOW_ONLY = "SHADOW_ONLY"
    REPLAY_VALIDATED = "REPLAY_VALIDATED"
    FORWARD_PAPER = "FORWARD_PAPER"
    CONTESTED_VALIDATED = "CONTESTED_VALIDATED"
    FILL_VALIDATED = "FILL_VALIDATED"
    CANARY_ELIGIBLE = "CANARY_ELIGIBLE"
    PROMOTED = "PROMOTED"
    DEGRADED = "DEGRADED"
    RETIRED = "RETIRED"


def _utc(value: datetime | str) -> datetime:
    try:
        parsed = (
            value
            if isinstance(value, datetime)
            else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        )
    except ValueError as exc:
        raise GenomeValidationError("genome timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GenomeValidationError("genome timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _unique(values: tuple[str, ...], *, name: str, required: bool) -> tuple[str, ...]:
    normalized = tuple(sorted(str(item).strip() for item in values))
    if (required and not normalized) or any(not item for item in normalized):
        raise GenomeValidationError(f"{name} contains an empty value")
    if len(set(normalized)) != len(normalized):
        raise GenomeValidationError(f"{name} contains duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class Gene:
    name: str
    category: GeneCategory
    value: Any
    version: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _GENE_NAME.fullmatch(self.name):
            raise GenomeValidationError(f"invalid gene name: {self.name!r}")
        if not self.version.strip():
            raise GenomeValidationError("gene version is required")
        evidence = _unique(self.evidence_ids, name="gene evidence", required=True)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "value", freeze_json(self.value))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "value": thaw_json(self.value),
            "version": self.version,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Gene:
        return cls(
            name=str(data["name"]),
            category=GeneCategory(str(data["category"])),
            value=data.get("value"),
            version=str(data["version"]),
            evidence_ids=tuple(data.get("evidence_ids", ())),
        )


@dataclass(frozen=True, slots=True)
class ForecastGenome:
    genome_id: str
    label: str
    vertical: str
    market_type: str
    horizon: str
    generation: int
    parent_genome_ids: tuple[str, ...]
    genes: tuple[Gene, ...]
    created_at: datetime
    evidence_ids: tuple[str, ...]
    status: GenomeStatus = GenomeStatus.EXPERIMENTAL

    def __post_init__(self) -> None:
        for field_name in ("label", "vertical", "market_type", "horizon"):
            if not getattr(self, field_name).strip():
                raise GenomeValidationError(f"{field_name} is required")
        if isinstance(self.generation, bool) or self.generation < 0:
            raise GenomeValidationError("genome generation must be non-negative")
        parents = _unique(
            self.parent_genome_ids,
            name="parent_genome_ids",
            required=self.generation > 0,
        )
        if self.generation == 0 and parents:
            raise GenomeValidationError("generation-zero genome cannot have parents")
        genes = tuple(sorted(self.genes, key=lambda item: item.name))
        if not genes or len({gene.name for gene in genes}) != len(genes):
            raise GenomeValidationError("genome genes must be non-empty and unique")
        evidence = _unique(self.evidence_ids, name="genome evidence", required=True)
        created = _utc(self.created_at)
        object.__setattr__(self, "parent_genome_ids", parents)
        object.__setattr__(self, "genes", genes)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "created_at", created)
        if self.genome_id != digest_json(self.semantic_dict()):
            raise GenomeValidationError("genome_id does not match canonical architecture")
        if self.status not in {GenomeStatus.EXPERIMENTAL, GenomeStatus.QUARANTINED}:
            raise GenomeValidationError(
                "new genome architecture must begin experimental or quarantined"
            )

    @classmethod
    def create(
        cls,
        *,
        label: str,
        vertical: str,
        market_type: str,
        horizon: str,
        generation: int,
        parent_genome_ids: tuple[str, ...],
        genes: tuple[Gene, ...],
        created_at: datetime,
        evidence_ids: tuple[str, ...],
        status: GenomeStatus = GenomeStatus.EXPERIMENTAL,
    ) -> ForecastGenome:
        semantic = {
            "schema_version": 1,
            "maturity": VNEXT_MATURITY,
            "label": label,
            "vertical": vertical,
            "market_type": market_type,
            "horizon": horizon,
            "generation": generation,
            "parent_genome_ids": sorted(parent_genome_ids),
            "genes": [item.to_dict() for item in sorted(genes, key=lambda x: x.name)],
            "created_at": _iso(created_at),
            "evidence_ids": sorted(evidence_ids),
            "status": status.value,
            "execution_authority": False,
            "promotion_authority": "HUMAN_ONLY",
        }
        return cls(
            genome_id=digest_json(semantic),
            label=label,
            vertical=vertical,
            market_type=market_type,
            horizon=horizon,
            generation=generation,
            parent_genome_ids=parent_genome_ids,
            genes=genes,
            created_at=created_at,
            evidence_ids=evidence_ids,
            status=status,
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "maturity": VNEXT_MATURITY,
            "label": self.label,
            "vertical": self.vertical,
            "market_type": self.market_type,
            "horizon": self.horizon,
            "generation": self.generation,
            "parent_genome_ids": list(self.parent_genome_ids),
            "genes": [item.to_dict() for item in self.genes],
            "created_at": _iso(self.created_at),
            "evidence_ids": list(self.evidence_ids),
            "status": self.status.value,
            "execution_authority": False,
            "promotion_authority": "HUMAN_ONLY",
        }

    def to_dict(self) -> dict[str, Any]:
        return {"genome_id": self.genome_id, **self.semantic_dict()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ForecastGenome:
        if data.get("execution_authority") is not False:
            raise GenomeValidationError("serialized genome has execution authority")
        if data.get("promotion_authority") != "HUMAN_ONLY":
            raise GenomeValidationError("serialized genome has promotion authority")
        return cls(
            genome_id=str(data["genome_id"]),
            label=str(data["label"]),
            vertical=str(data["vertical"]),
            market_type=str(data["market_type"]),
            horizon=str(data["horizon"]),
            generation=int(data["generation"]),
            parent_genome_ids=tuple(data.get("parent_genome_ids", ())),
            genes=tuple(Gene.from_dict(item) for item in data.get("genes", ())),
            created_at=_utc(data["created_at"]),
            evidence_ids=tuple(data.get("evidence_ids", ())),
            status=GenomeStatus(str(data["status"])),
        )


__all__ = [
    "ForecastGenome",
    "Gene",
    "GeneCategory",
    "GenomeStatus",
    "GenomeValidationError",
]
