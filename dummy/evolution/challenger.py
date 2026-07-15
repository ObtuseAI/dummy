"""Quarantined challenger records connect proposals to candidate genomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dummy.genome import ForecastGenome, GenomeMutationProposal
from dummy.world_model.models import digest_json


@dataclass(frozen=True, slots=True)
class EvolutionChallenger:
    challenger_id: str
    proposal: GenomeMutationProposal
    genome: ForecastGenome

    def __post_init__(self) -> None:
        if not self.proposal.allowed_by_constitution:
            raise ValueError("blocked proposal cannot become a challenger")
        if self.proposal.candidate_genome != self.genome:
            raise ValueError("challenger genome differs from its proposal")
        if self.challenger_id != digest_json(self.semantic_dict()):
            raise ValueError("challenger ID mismatch")

    @classmethod
    def create(cls, proposal: GenomeMutationProposal) -> EvolutionChallenger:
        if proposal.candidate_genome is None:
            raise ValueError("mutation proposal did not materialize a candidate")
        semantic = {
            "schema_version": 1,
            "proposal_id": proposal.proposal_id,
            "genome_id": proposal.candidate_genome.genome_id,
            "status": "QUARANTINED_RESEARCH_CHALLENGER",
            "runtime_applied": False,
            "execution_authority": False,
            "promotion_authority": "HUMAN_ONLY",
        }
        return cls(
            challenger_id=digest_json(semantic),
            proposal=proposal,
            genome=proposal.candidate_genome,
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "proposal_id": self.proposal.proposal_id,
            "genome_id": self.genome.genome_id,
            "status": "QUARANTINED_RESEARCH_CHALLENGER",
            "runtime_applied": False,
            "execution_authority": False,
            "promotion_authority": "HUMAN_ONLY",
        }

    def to_dict(self) -> dict[str, Any]:
        return {"challenger_id": self.challenger_id, **self.semantic_dict()}


__all__ = ["EvolutionChallenger"]
