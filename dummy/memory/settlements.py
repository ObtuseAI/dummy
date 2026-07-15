"""Settlement memory accepts verified outcome truth only."""

from __future__ import annotations

from datetime import datetime

from dummy.organisms.models import VerifiedSettlement

from .schema import EvidenceReality, MemoryKind, MemoryRecord


def settlement_memory(
    settlement: VerifiedSettlement,
    *,
    recorded_at: datetime,
    causal_parent_ids: tuple[str, ...] = (),
) -> MemoryRecord:
    return MemoryRecord.create(
        kind=MemoryKind.SETTLEMENT,
        entity_id=settlement.market_id,
        event_cluster_id=settlement.event_cluster_id,
        observed_at=settlement.market_closed_at,
        received_at=settlement.received_at,
        recorded_at=recorded_at,
        source=settlement.source,
        source_reference=settlement.source_reference,
        evidence_reality=EvidenceReality.VERIFIED_SETTLEMENT,
        provenance_verified=settlement.verified,
        causal_parent_ids=causal_parent_ids,
        evidence_ids=(settlement.source_reference,),
        payload=settlement.to_dict(),
    )


__all__ = ["settlement_memory"]
