"""Level-4/5 meta-policy challengers remain externally judged proposals."""

from __future__ import annotations

from datetime import datetime

from dummy.genome import (
    ForecastGenome,
    GeneCategory,
    GenomeMutationProposal,
    GenomeValidationError,
    MutationLevel,
    MutationOperation,
    propose_mutation,
)


def propose_meta_policy_challenger(
    base: ForecastGenome,
    *,
    level: MutationLevel,
    operations: tuple[MutationOperation, ...],
    target_paths: tuple[str, ...],
    created_at: datetime,
    evidence_ids: tuple[str, ...],
) -> GenomeMutationProposal:
    expected = (
        GeneCategory.METACOGNITIVE_POLICY
        if level is MutationLevel.METACOGNITIVE_CONTROL
        else GeneCategory.MUTATION_POLICY
        if level is MutationLevel.MUTATION_SELECTION_POLICY
        else None
    )
    if expected is None or any(item.category is not expected for item in operations):
        raise GenomeValidationError(
            "meta evolution accepts only level-4 metacognition or level-5 mutation policy"
        )
    proposal = propose_mutation(
        base,
        level=level,
        operations=operations,
        target_paths=target_paths,
        created_at=created_at,
        evidence_ids=evidence_ids,
    )
    if proposal.candidate_genome is not None and proposal.candidate_genome.genome_id == base.genome_id:
        raise GenomeValidationError("meta-policy challenger did not change architecture")
    return proposal


__all__ = ["propose_meta_policy_challenger"]
