"""Held-out fitness evidence remains separate from genome architecture identity."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from dummy.world_model.models import digest_json

from .schema import GenomeValidationError


@dataclass(frozen=True, slots=True)
class GenomeFitness:
    fitness_id: str
    genome_id: str
    evaluator_version: str
    held_out_event_clusters: int
    raw_brier_gain: float | None
    cluster_adjusted_gain: float | None
    confidence_interval: tuple[float, float] | None
    corrected_p_value: float | None
    transfer_passed: bool
    governance_preserved: bool
    verdict: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.genome_id.strip() or not self.evaluator_version.strip():
            raise GenomeValidationError("fitness identity is required")
        if self.held_out_event_clusters < 0:
            raise GenomeValidationError("fitness cluster count cannot be negative")
        for field_name in (
            "raw_brier_gain",
            "cluster_adjusted_gain",
            "corrected_p_value",
        ):
            value = getattr(self, field_name)
            if value is not None and not math.isfinite(float(value)):
                raise GenomeValidationError(f"{field_name} must be finite")
        if self.corrected_p_value is not None and not 0.0 <= self.corrected_p_value <= 1.0:
            raise GenomeValidationError("corrected p-value must be in [0, 1]")
        if self.confidence_interval is not None:
            low, high = self.confidence_interval
            if not all(math.isfinite(float(item)) for item in (low, high)) or low > high:
                raise GenomeValidationError("fitness confidence interval is invalid")
        evidence = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        if not evidence or any(not item for item in evidence):
            raise GenomeValidationError("fitness evidence is required")
        object.__setattr__(self, "evidence_ids", evidence)
        if self.verdict == "HELD_OUT_IMPROVEMENT_SUPPORTED" and (
            self.confidence_interval is None
            or self.confidence_interval[0] <= 0.0
            or self.corrected_p_value is None
            or self.corrected_p_value > 0.05
            or not self.transfer_passed
            or not self.governance_preserved
        ):
            raise GenomeValidationError("supported fitness verdict lacks required gates")
        if self.fitness_id != digest_json(self.semantic_dict()):
            raise GenomeValidationError("fitness ID does not match its evidence")

    @classmethod
    def create(cls, **kwargs: Any) -> GenomeFitness:
        semantic = cls._semantic_from(kwargs)
        return cls(fitness_id=digest_json(semantic), **kwargs)

    @staticmethod
    def _semantic_from(data: Mapping[str, Any]) -> dict[str, Any]:
        interval = data.get("confidence_interval")
        return {
            "schema_version": 1,
            "genome_id": data["genome_id"],
            "evaluator_version": data["evaluator_version"],
            "held_out_event_clusters": data["held_out_event_clusters"],
            "raw_brier_gain": data.get("raw_brier_gain"),
            "cluster_adjusted_gain": data.get("cluster_adjusted_gain"),
            "confidence_interval": list(interval) if interval is not None else None,
            "corrected_p_value": data.get("corrected_p_value"),
            "transfer_passed": data["transfer_passed"],
            "governance_preserved": data["governance_preserved"],
            "verdict": data["verdict"],
            "evidence_ids": sorted(data["evidence_ids"]),
        }

    def semantic_dict(self) -> dict[str, Any]:
        return self._semantic_from(
            {
                "genome_id": self.genome_id,
                "evaluator_version": self.evaluator_version,
                "held_out_event_clusters": self.held_out_event_clusters,
                "raw_brier_gain": self.raw_brier_gain,
                "cluster_adjusted_gain": self.cluster_adjusted_gain,
                "confidence_interval": self.confidence_interval,
                "corrected_p_value": self.corrected_p_value,
                "transfer_passed": self.transfer_passed,
                "governance_preserved": self.governance_preserved,
                "verdict": self.verdict,
                "evidence_ids": self.evidence_ids,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {"fitness_id": self.fitness_id, **self.semantic_dict()}


__all__ = ["GenomeFitness"]
