"""The forecast object improved by, but isolated from, the outer researcher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dummy.constitution import Authority, assert_authority_at_most
from dummy.genome import ForecastGenome
from dummy.organisms import OrganismTemplate
from dummy.world_model.models import digest_json

from .models import AutoresearchValidationError


@dataclass(frozen=True, slots=True)
class InnerForecastOrganism:
    organism_id: str
    genome: ForecastGenome
    template_id: str
    template_digest: str
    lineage_id: str
    authority: Authority = Authority.FORECAST

    def __post_init__(self) -> None:
        if not self.template_id.strip() or not self.lineage_id.strip():
            raise AutoresearchValidationError("inner organism identity is required")
        assert_authority_at_most(
            self.authority,
            Authority.SIMULATE,
            component="inner forecast research organism",
        )
        if self.organism_id != digest_json(self.semantic_dict()):
            raise AutoresearchValidationError("inner organism ID mismatch")

    @classmethod
    def create(
        cls,
        *,
        genome: ForecastGenome,
        template: OrganismTemplate,
        lineage_id: str,
        authority: Authority = Authority.FORECAST,
    ) -> InnerForecastOrganism:
        semantic = {
            "schema_version": 1,
            "genome_id": genome.genome_id,
            "template_id": template.template_id,
            "template_digest": template.digest(),
            "lineage_id": lineage_id,
            "authority": authority.name,
            "private_evaluator_access": False,
            "execution_authority": False,
            "promotion_authority": "HUMAN_ONLY",
        }
        return cls(
            organism_id=digest_json(semantic),
            genome=genome,
            template_id=template.template_id,
            template_digest=template.digest(),
            lineage_id=lineage_id,
            authority=authority,
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "genome_id": self.genome.genome_id,
            "template_id": self.template_id,
            "template_digest": self.template_digest,
            "lineage_id": self.lineage_id,
            "authority": self.authority.name,
            "private_evaluator_access": False,
            "execution_authority": False,
            "promotion_authority": "HUMAN_ONLY",
        }

    def to_dict(self) -> dict[str, Any]:
        return {"organism_id": self.organism_id, **self.semantic_dict()}


__all__ = ["InnerForecastOrganism"]
