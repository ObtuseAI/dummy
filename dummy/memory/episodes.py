"""Episode memory captures a dissolved forecast lifecycle without rewriting it."""

from __future__ import annotations

from datetime import datetime

from dummy.organisms.models import EpisodeArtifact, EpisodeStatus

from .schema import EvidenceReality, MemoryKind, MemoryRecord, MemoryValidationError


def episode_memory(
    artifact: EpisodeArtifact,
    *,
    recorded_at: datetime,
    causal_parent_ids: tuple[str, ...],
) -> MemoryRecord:
    payload = artifact.to_dict()
    if payload.get("status") != EpisodeStatus.DISSOLVED.value:
        raise MemoryValidationError("episode memory requires a dissolved artifact")
    settlement = payload.get("settlement") or {}
    return MemoryRecord.create(
        kind=MemoryKind.EPISODE,
        entity_id=artifact.episode_id,
        event_cluster_id=str(payload["event_cluster_id"]),
        observed_at=payload["decision_at"],
        received_at=settlement["received_at"],
        recorded_at=recorded_at,
        source="dummy-vnext-organism",
        source_reference=f"episode://{artifact.episode_id}",
        evidence_reality=EvidenceReality.DERIVED,
        provenance_verified=True,
        causal_parent_ids=causal_parent_ids,
        evidence_ids=(
            artifact.episode_id,
            str(payload["issuance_digest"]),
            str(settlement["source_reference"]),
        ),
        payload=payload,
    )


__all__ = ["episode_memory"]
