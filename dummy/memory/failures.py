"""Failure memory records falsification and operational failure without erasure."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .schema import EvidenceReality, MemoryKind, MemoryRecord


class FailureKind(str, Enum):
    FORECAST_ERROR = "FORECAST_ERROR"
    CALIBRATION_ERROR = "CALIBRATION_ERROR"
    DATA_GAP = "DATA_GAP"
    LEAKAGE = "LEAKAGE"
    REGIME_FAILURE = "REGIME_FAILURE"
    EXECUTION_ASSUMPTION = "EXECUTION_ASSUMPTION"
    RESOURCE_WASTE = "RESOURCE_WASTE"
    GOVERNANCE_VIOLATION = "GOVERNANCE_VIOLATION"


def failure_memory(
    *,
    failure_id: str,
    event_cluster_id: str | None,
    occurred_at: datetime,
    recorded_at: datetime,
    kind: FailureKind,
    reason: str,
    source_reference: str,
    evidence_ids: tuple[str, ...],
    causal_parent_ids: tuple[str, ...],
    reversible: bool,
    details: Mapping[str, Any] | None = None,
) -> MemoryRecord:
    if not reason.strip():
        raise ValueError("failure reason is required")
    return MemoryRecord.create(
        kind=MemoryKind.FAILURE,
        entity_id=failure_id,
        event_cluster_id=event_cluster_id,
        observed_at=occurred_at,
        received_at=occurred_at,
        recorded_at=recorded_at,
        source="dummy-vnext-failure-analysis",
        source_reference=source_reference,
        evidence_reality=EvidenceReality.DERIVED,
        provenance_verified=True,
        causal_parent_ids=causal_parent_ids,
        evidence_ids=evidence_ids,
        payload={
            "failure_kind": kind.value,
            "reason": reason,
            "reversible": reversible,
            "details": dict(details or {}),
        },
    )


__all__ = ["FailureKind", "failure_memory"]
