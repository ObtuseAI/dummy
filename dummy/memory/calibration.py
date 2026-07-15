"""Calibration memory joins forecasts to verified realized outcomes."""

from __future__ import annotations

import math
from datetime import datetime

from .schema import EvidenceReality, MemoryKind, MemoryRecord, MemoryValidationError


def calibration_memory(
    *,
    calibration_id: str,
    event_cluster_id: str,
    probability_yes: float,
    result_yes: bool,
    model_version: str,
    calibration_version: str,
    settled_at: datetime,
    received_at: datetime,
    recorded_at: datetime,
    settlement_source_reference: str,
    evidence_ids: tuple[str, ...],
    causal_parent_ids: tuple[str, ...],
) -> MemoryRecord:
    probability = float(probability_yes)
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise MemoryValidationError("calibration probability must be in [0, 1]")
    if type(result_yes) is not bool:
        raise MemoryValidationError("calibration outcome must be boolean")
    if not model_version.strip() or not calibration_version.strip():
        raise MemoryValidationError("calibration versions are required")
    brier = (probability - float(result_yes)) ** 2
    return MemoryRecord.create(
        kind=MemoryKind.CALIBRATION,
        entity_id=calibration_id,
        event_cluster_id=event_cluster_id,
        observed_at=settled_at,
        received_at=received_at,
        recorded_at=recorded_at,
        source="dummy-vnext-calibration",
        source_reference=settlement_source_reference,
        evidence_reality=EvidenceReality.DERIVED,
        provenance_verified=True,
        causal_parent_ids=causal_parent_ids,
        evidence_ids=evidence_ids,
        payload={
            "probability_yes": probability,
            "result_yes": result_yes,
            "brier": round(brier, 12),
            "model_version": model_version,
            "calibration_version": calibration_version,
            "settlement_verified": True,
        },
    )


__all__ = ["calibration_memory"]
