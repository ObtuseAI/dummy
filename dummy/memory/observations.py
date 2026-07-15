"""Observation memory preserves raw point-in-time evidence and provenance."""

from __future__ import annotations

from datetime import datetime

from dummy.organisms.models import PointInTimeEvidence

from .schema import EvidenceReality, MemoryKind, MemoryRecord


def observation_memory(
    evidence: PointInTimeEvidence,
    *,
    recorded_at: datetime,
    event_cluster_id: str | None = None,
) -> MemoryRecord:
    return MemoryRecord.create(
        kind=MemoryKind.OBSERVATION,
        entity_id=evidence.evidence_id,
        event_cluster_id=event_cluster_id,
        observed_at=evidence.observed_at,
        received_at=evidence.received_at,
        recorded_at=recorded_at,
        source=evidence.source_family,
        source_reference=evidence.source_reference,
        evidence_reality=EvidenceReality.PUBLIC_OBSERVATION,
        provenance_verified=(
            evidence.observed_at_verified and evidence.received_at_verified
        ),
        causal_parent_ids=(),
        evidence_ids=(evidence.evidence_id,),
        payload=evidence.to_dict(),
    )


__all__ = ["observation_memory"]
