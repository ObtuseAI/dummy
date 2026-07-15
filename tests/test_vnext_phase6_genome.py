from __future__ import annotations

from datetime import datetime, timezone

import pytest

from dummy.genome import (
    ForecastGenome,
    Gene,
    GeneCategory,
    GenomeRegistry,
    GenomeValidationError,
    MutationLevel,
    MutationOperation,
    MutationOperator,
    RetirementAction,
    RetirementRecord,
    genome_catalog_manifest,
    inherit_genome,
    lineage_report,
    pilot_genomes,
    propose_mutation,
)
from dummy.memory import EvidenceReality, genome_memory


NOW = datetime(2026, 7, 15, 2, 0, tzinfo=timezone.utc)


def _base(value: float = 0.5) -> ForecastGenome:
    gene = Gene(
        name="market.anchor",
        category=GeneCategory.MARKET_PRIOR_WEIGHT,
        value=value,
        version="v1",
        evidence_ids=("training-evidence",),
    )
    return ForecastGenome.create(
        label="phase6 test base",
        vertical="CRYPTO",
        market_type="BTC_15M",
        horizon="15m",
        generation=0,
        parent_genome_ids=(),
        genes=(gene,),
        created_at=NOW,
        evidence_ids=("training-evidence",),
    )


def _operation(value: float = 0.6) -> MutationOperation:
    return MutationOperation(
        operator=MutationOperator.SET,
        gene_name="market.anchor",
        category=GeneCategory.MARKET_PRIOR_WEIGHT,
        value=value,
        gene_version="v2",
        rationale="test a stronger market anchor",
    )


def test_pilot_catalog_is_deterministic_and_claim_free() -> None:
    first = genome_catalog_manifest()
    second = genome_catalog_manifest()
    assert first == second
    assert first["genome_count"] == 2
    assert first["performance_claim_supported"] is False
    assert first["runtime_applied"] is False
    assert all(len(item["genes"]) == 13 for item in first["genomes"])


def test_registry_requires_known_scope_consistent_lineage() -> None:
    registry = GenomeRegistry()
    base = _base()
    registry.register(base)
    proposal = propose_mutation(
        base,
        level=MutationLevel.PARAMETERS,
        operations=(_operation(),),
        target_paths=("dummy/genome/candidates/test.json",),
        created_at=NOW,
        evidence_ids=("selection-evidence",),
    )
    assert proposal.candidate_genome is not None
    registry.register(proposal.candidate_genome)
    report = lineage_report(registry)
    assert report["roots"] == [base.genome_id]
    assert report["leaves"] == [proposal.candidate_genome.genome_id]


def test_mutation_is_proposal_only_and_protected_paths_never_materialize() -> None:
    base = _base()
    allowed = propose_mutation(
        base,
        level=MutationLevel.PARAMETERS,
        operations=(_operation(),),
        target_paths=("dummy/genome/candidates/test.json",),
        created_at=NOW,
        evidence_ids=("selection-evidence",),
    )
    assert allowed.allowed_by_constitution is True
    assert allowed.candidate_genome is not None
    assert allowed.to_dict()["applied"] is False
    assert allowed.to_dict()["automatic_promotion"] is False

    blocked = propose_mutation(
        base,
        level=MutationLevel.PARAMETERS,
        operations=(_operation(),),
        target_paths=("dummy/evolution/evaluator.py",),
        created_at=NOW,
        evidence_ids=("selection-evidence",),
    )
    assert blocked.allowed_by_constitution is False
    assert blocked.candidate_genome is None
    assert blocked.blocked_paths == ("dummy/evolution/evaluator.py",)


def test_recursive_level_cannot_mutate_a_higher_level_category() -> None:
    base = _base()
    invalid = MutationOperation(
        operator=MutationOperator.SET,
        gene_name="market.anchor",
        category=GeneCategory.METACOGNITIVE_POLICY,
        value="unsafe",
        gene_version="v2",
        rationale="invalid category",
    )
    with pytest.raises(GenomeValidationError, match="recursive level"):
        propose_mutation(
            base,
            level=MutationLevel.PARAMETERS,
            operations=(invalid,),
            target_paths=("dummy/genome/candidates/test.json",),
            created_at=NOW,
            evidence_ids=("selection-evidence",),
        )


def test_inheritance_requires_explicit_conflict_resolution() -> None:
    left, right = _base(0.5), _base(0.6)
    with pytest.raises(GenomeValidationError, match="explicit override"):
        inherit_genome(
            (left, right),
            label="conflicted child",
            created_at=NOW,
            evidence_ids=("cross-evidence",),
        )
    override = Gene(
        name="market.anchor",
        category=GeneCategory.MARKET_PRIOR_WEIGHT,
        value=0.55,
        version="resolved-v1",
        evidence_ids=("cross-evidence",),
    )
    child = inherit_genome(
        (left, right),
        label="resolved child",
        created_at=NOW,
        evidence_ids=("cross-evidence",),
        overrides={"market.anchor": override},
    )
    assert child.parent_genome_ids == tuple(sorted((left.genome_id, right.genome_id)))
    assert child.generation == 1


def test_genome_memory_and_retirement_are_non_promoting_proposals() -> None:
    genome = pilot_genomes()[0]
    memory = genome_memory(genome, recorded_at=NOW)
    assert memory.evidence_reality is EvidenceReality.HYPOTHESIS
    assert memory.payload["performance_claim_supported"] is False
    retirement = RetirementRecord.create(
        genome_id=genome.genome_id,
        genome_version="v1",
        action=RetirementAction.QUARANTINE,
        reason="forward evidence degraded",
        replacement_genome_id=None,
        reversible=True,
        last_healthy_fitness_id="fitness-healthy",
        evidence_ids=("fitness-degraded",),
        decided_at=NOW,
    )
    assert retirement.applied is False
    assert retirement.to_dict()["automatic_promotion"] is False
