"""Deterministic, reversible retirement and quarantine proposal records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from dummy.world_model.models import digest_json

from .schema import GenomeValidationError


class RetirementAction(str, Enum):
    QUARANTINE = "QUARANTINE"
    RETIRE = "RETIRE"


@dataclass(frozen=True, slots=True)
class RetirementRecord:
    retirement_id: str
    genome_id: str
    genome_version: str
    action: RetirementAction
    reason: str
    replacement_genome_id: str | None
    reversible: bool
    last_healthy_fitness_id: str | None
    evidence_ids: tuple[str, ...]
    decided_at: datetime
    applied: bool = False

    def __post_init__(self) -> None:
        if not self.genome_id.strip() or not self.genome_version.strip():
            raise GenomeValidationError("retirement genome identity is required")
        if not self.reason.strip():
            raise GenomeValidationError("retirement reason is required")
        evidence = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        if not evidence or any(not item for item in evidence):
            raise GenomeValidationError("retirement evidence is required")
        decided = self.decided_at
        if decided.tzinfo is None or decided.utcoffset() is None:
            raise GenomeValidationError("retirement time must be timezone-aware")
        decided = decided.astimezone(timezone.utc)
        if self.applied:
            raise GenomeValidationError(
                "Phase 6 retirement records are proposal-only until registry integration"
            )
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "decided_at", decided)
        if self.retirement_id != digest_json(self.semantic_dict()):
            raise GenomeValidationError("retirement ID mismatch")

    @classmethod
    def create(
        cls,
        *,
        genome_id: str,
        genome_version: str,
        action: RetirementAction,
        reason: str,
        replacement_genome_id: str | None,
        reversible: bool,
        last_healthy_fitness_id: str | None,
        evidence_ids: tuple[str, ...],
        decided_at: datetime,
    ) -> RetirementRecord:
        if decided_at.tzinfo is None or decided_at.utcoffset() is None:
            raise GenomeValidationError("retirement time must be timezone-aware")
        semantic = {
            "schema_version": 1,
            "genome_id": genome_id,
            "genome_version": genome_version,
            "action": action.value,
            "reason": reason,
            "replacement_genome_id": replacement_genome_id,
            "reversible": reversible,
            "last_healthy_fitness_id": last_healthy_fitness_id,
            "evidence_ids": sorted(evidence_ids),
            "decided_at": decided_at.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "applied": False,
            "automatic_promotion": False,
            "execution_authority": False,
        }
        return cls(
            retirement_id=digest_json(semantic),
            genome_id=genome_id,
            genome_version=genome_version,
            action=action,
            reason=reason,
            replacement_genome_id=replacement_genome_id,
            reversible=reversible,
            last_healthy_fitness_id=last_healthy_fitness_id,
            evidence_ids=evidence_ids,
            decided_at=decided_at,
            applied=False,
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "genome_id": self.genome_id,
            "genome_version": self.genome_version,
            "action": self.action.value,
            "reason": self.reason,
            "replacement_genome_id": self.replacement_genome_id,
            "reversible": self.reversible,
            "last_healthy_fitness_id": self.last_healthy_fitness_id,
            "evidence_ids": list(self.evidence_ids),
            "decided_at": self.decided_at.isoformat().replace("+00:00", "Z"),
            "applied": False,
            "automatic_promotion": False,
            "execution_authority": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"retirement_id": self.retirement_id, **self.semantic_dict()}


__all__ = ["RetirementAction", "RetirementRecord"]
