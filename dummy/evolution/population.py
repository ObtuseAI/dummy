"""Bounded deterministic population assembled from allowed proposals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dummy.genome import ForecastGenome, GenomeMutationProposal
from dummy.world_model.models import digest_json


@dataclass(frozen=True, slots=True)
class CandidatePopulation:
    population_id: str
    generation: int
    genomes: tuple[ForecastGenome, ...]
    proposal_ids: tuple[str, ...]
    maximum_size: int

    def __post_init__(self) -> None:
        genomes = tuple(sorted(self.genomes, key=lambda item: item.genome_id))
        proposals = tuple(sorted(self.proposal_ids))
        if not genomes or len(genomes) > self.maximum_size:
            raise ValueError("candidate population violates its size bound")
        if len({item.genome_id for item in genomes}) != len(genomes):
            raise ValueError("candidate population contains duplicate genomes")
        if len(proposals) != len(genomes) or len(set(proposals)) != len(proposals):
            raise ValueError("candidate population requires one unique proposal per genome")
        if any(item.generation != self.generation for item in genomes):
            raise ValueError("candidate population mixes generations")
        object.__setattr__(self, "genomes", genomes)
        object.__setattr__(self, "proposal_ids", proposals)
        if self.population_id != digest_json(self.semantic_dict()):
            raise ValueError("candidate population ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "generation": self.generation,
            "genome_ids": [item.genome_id for item in self.genomes],
            "proposal_ids": list(self.proposal_ids),
            "maximum_size": self.maximum_size,
            "runtime_applied": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"population_id": self.population_id, **self.semantic_dict()}


def build_population(
    proposals: tuple[GenomeMutationProposal, ...],
    *,
    maximum_size: int = 32,
) -> CandidatePopulation:
    allowed = tuple(
        sorted(
            (
                proposal
                for proposal in proposals
                if proposal.allowed_by_constitution
                and proposal.candidate_genome is not None
            ),
            key=lambda item: item.proposal_id,
        )
    )
    if not allowed:
        raise ValueError("population has no constitutionally allowed candidates")
    selected = allowed[:maximum_size]
    genomes = tuple(item.candidate_genome for item in selected)
    if any(item is None for item in genomes):
        raise ValueError("allowed proposal lacks a candidate genome")
    candidates = tuple(item for item in genomes if item is not None)
    semantic = {
        "schema_version": 1,
        "generation": candidates[0].generation,
        "genome_ids": sorted(item.genome_id for item in candidates),
        "proposal_ids": sorted(item.proposal_id for item in selected),
        "maximum_size": maximum_size,
        "runtime_applied": False,
    }
    return CandidatePopulation(
        population_id=digest_json(semantic),
        generation=candidates[0].generation,
        genomes=candidates,
        proposal_ids=tuple(item.proposal_id for item in selected),
        maximum_size=maximum_size,
    )


__all__ = ["CandidatePopulation", "build_population"]
