"""Strategy memory records where an organism or genome was evaluated."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Mapping

from .schema import EvidenceReality, MemoryKind, MemoryRecord, MemoryValidationError


def strategy_memory(
    *,
    strategy_id: str,
    vertical: str,
    market_type: str,
    regime: str,
    evaluated_at: datetime,
    recorded_at: datetime,
    settled_event_clusters: int,
    metrics: Mapping[str, Any],
    claim_supported: bool,
    evidence_ids: tuple[str, ...],
    causal_parent_ids: tuple[str, ...],
) -> MemoryRecord:
    if any(not value.strip() for value in (vertical, market_type, regime)):
        raise MemoryValidationError("strategy scope is incomplete")
    if isinstance(settled_event_clusters, bool) or settled_event_clusters < 0:
        raise MemoryValidationError("strategy cluster count must be non-negative")
    if claim_supported and settled_event_clusters == 0:
        raise MemoryValidationError("strategy claim requires settled event clusters")
    for value in metrics.values():
        if isinstance(value, float) and not math.isfinite(value):
            raise MemoryValidationError("strategy metrics contain non-finite values")
    return MemoryRecord.create(
        kind=MemoryKind.STRATEGY,
        entity_id=strategy_id,
        event_cluster_id=None,
        observed_at=evaluated_at,
        received_at=evaluated_at,
        recorded_at=recorded_at,
        source="dummy-vnext-strategy-evaluator",
        source_reference=f"strategy://{strategy_id}",
        evidence_reality=EvidenceReality.DERIVED,
        provenance_verified=True,
        causal_parent_ids=causal_parent_ids,
        evidence_ids=evidence_ids,
        payload={
            "vertical": vertical,
            "market_type": market_type,
            "regime": regime,
            "settled_event_clusters": settled_event_clusters,
            "metrics": dict(metrics),
            "claim_supported": claim_supported,
        },
    )


__all__ = ["strategy_memory"]
