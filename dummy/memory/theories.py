"""Theory memory keeps cross-market patterns hypothetical until repeated evidence."""

from __future__ import annotations

from datetime import datetime

from .schema import EvidenceReality, MemoryKind, MemoryRecord, MemoryValidationError


def theory_memory(
    *,
    theory_id: str,
    statement: str,
    proposed_at: datetime,
    recorded_at: datetime,
    event_cluster_ids: tuple[str, ...],
    evidence_ids: tuple[str, ...],
    causal_parent_ids: tuple[str, ...],
) -> MemoryRecord:
    if not statement.strip():
        raise MemoryValidationError("theory statement is required")
    clusters = tuple(sorted(str(item).strip() for item in event_cluster_ids))
    if any(not item for item in clusters) or len(set(clusters)) != len(clusters):
        raise MemoryValidationError("theory event clusters must be unique")
    repeated = len(clusters) >= 2
    return MemoryRecord.create(
        kind=MemoryKind.THEORY,
        entity_id=theory_id,
        event_cluster_id=None,
        observed_at=proposed_at,
        received_at=proposed_at,
        recorded_at=recorded_at,
        source="dummy-vnext-theory-memory",
        source_reference=f"theory://{theory_id}",
        evidence_reality=(
            EvidenceReality.DERIVED if repeated else EvidenceReality.HYPOTHESIS
        ),
        provenance_verified=repeated,
        causal_parent_ids=causal_parent_ids,
        evidence_ids=evidence_ids,
        payload={
            "statement": statement,
            "event_cluster_ids": list(clusters),
            "support_state": (
                "REPEATED_EVIDENCE_NOT_CAUSAL_PROOF" if repeated else "HYPOTHESIS_ONLY"
            ),
            "promotion_eligible": False,
        },
    )


__all__ = ["theory_memory"]
