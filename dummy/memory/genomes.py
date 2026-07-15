"""Genome memory records reusable architectures as hypotheses, not winners."""

from __future__ import annotations

from datetime import datetime

from dummy.genome.schema import ForecastGenome

from .schema import EvidenceReality, MemoryKind, MemoryRecord


def genome_memory(
    genome: ForecastGenome,
    *,
    recorded_at: datetime,
    causal_parent_ids: tuple[str, ...] = (),
) -> MemoryRecord:
    return MemoryRecord.create(
        kind=MemoryKind.GENOME,
        entity_id=genome.genome_id,
        event_cluster_id=None,
        observed_at=genome.created_at,
        received_at=genome.created_at,
        recorded_at=recorded_at,
        source="dummy-vnext-genome-registry",
        source_reference=f"genome://{genome.genome_id}",
        evidence_reality=EvidenceReality.HYPOTHESIS,
        provenance_verified=False,
        causal_parent_ids=causal_parent_ids,
        evidence_ids=genome.evidence_ids,
        payload={
            **genome.to_dict(),
            "performance_claim_supported": False,
            "runtime_applied": False,
        },
    )


__all__ = ["genome_memory"]
