"""Immutable, content-addressed records for DUMMY vNext causal memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from dummy.world_model.models import canonical_json, digest_json, freeze_json, thaw_json


class MemoryValidationError(ValueError):
    """A memory record is malformed, noncausal, or overstates its evidence."""


class MemoryKind(str, Enum):
    OBSERVATION = "OBSERVATION"
    EPISODE = "EPISODE"
    SETTLEMENT = "SETTLEMENT"
    FILL = "FILL"
    FAILURE = "FAILURE"
    CALIBRATION = "CALIBRATION"
    STRATEGY = "STRATEGY"
    THEORY = "THEORY"
    GENOME = "GENOME"


class EvidenceReality(str, Enum):
    PUBLIC_OBSERVATION = "PUBLIC_OBSERVATION"
    VERIFIED_SETTLEMENT = "VERIFIED_SETTLEMENT"
    WITNESSED_FILL = "WITNESSED_FILL"
    SIMULATED = "SIMULATED"
    DERIVED = "DERIVED"
    HYPOTHESIS = "HYPOTHESIS"


REALIZED_REALITIES = frozenset(
    {EvidenceReality.VERIFIED_SETTLEMENT, EvidenceReality.WITNESSED_FILL}
)


def _utc(value: datetime | str) -> datetime:
    try:
        parsed = (
            value
            if isinstance(value, datetime)
            else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        )
    except ValueError as exc:
        raise MemoryValidationError("memory timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MemoryValidationError("memory timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _unique(values: tuple[str, ...], *, name: str, required: bool) -> tuple[str, ...]:
    normalized = tuple(sorted(str(item).strip() for item in values))
    if (required and not normalized) or any(not item for item in normalized):
        raise MemoryValidationError(f"{name} contains an empty value")
    if len(set(normalized)) != len(normalized):
        raise MemoryValidationError(f"{name} contains duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: str
    kind: MemoryKind
    entity_id: str
    event_cluster_id: str | None
    observed_at: datetime
    received_at: datetime
    recorded_at: datetime
    source: str
    source_reference: str
    evidence_reality: EvidenceReality
    provenance_verified: bool
    causal_parent_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        for field_name in ("entity_id", "source", "source_reference"):
            if not getattr(self, field_name).strip():
                raise MemoryValidationError(f"{field_name} is required")
        cluster = (
            str(self.event_cluster_id).strip()
            if self.event_cluster_id is not None
            else None
        )
        if cluster == "":
            raise MemoryValidationError("event_cluster_id cannot be blank")
        observed = _utc(self.observed_at)
        received = _utc(self.received_at)
        recorded = _utc(self.recorded_at)
        if observed > received or received > recorded:
            raise MemoryValidationError(
                "memory requires observed_at <= received_at <= recorded_at"
            )
        parents = _unique(
            self.causal_parent_ids,
            name="causal_parent_ids",
            required=False,
        )
        evidence = _unique(self.evidence_ids, name="evidence_ids", required=True)
        if self.memory_id in parents:
            raise MemoryValidationError("memory cannot be its own causal parent")
        if self.evidence_reality in REALIZED_REALITIES and not self.provenance_verified:
            raise MemoryValidationError("realized memory requires verified provenance")
        if (
            self.kind is MemoryKind.SETTLEMENT
            and self.evidence_reality is not EvidenceReality.VERIFIED_SETTLEMENT
        ):
            raise MemoryValidationError("settlement memory must be verified realization")
        frozen = freeze_json(self.payload)
        object.__setattr__(self, "event_cluster_id", cluster)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "received_at", received)
        object.__setattr__(self, "recorded_at", recorded)
        object.__setattr__(self, "causal_parent_ids", parents)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "payload", frozen)
        expected = digest_json(self.semantic_dict())
        if self.memory_id != expected:
            raise MemoryValidationError("memory_id does not match canonical content")

    @classmethod
    def create(
        cls,
        *,
        kind: MemoryKind,
        entity_id: str,
        event_cluster_id: str | None,
        observed_at: datetime,
        received_at: datetime,
        recorded_at: datetime,
        source: str,
        source_reference: str,
        evidence_reality: EvidenceReality,
        provenance_verified: bool,
        causal_parent_ids: tuple[str, ...],
        evidence_ids: tuple[str, ...],
        payload: Mapping[str, Any],
    ) -> MemoryRecord:
        semantic = {
            "schema_version": 1,
            "kind": kind.value,
            "entity_id": entity_id,
            "event_cluster_id": event_cluster_id,
            "observed_at": _iso(observed_at),
            "received_at": _iso(received_at),
            "recorded_at": _iso(recorded_at),
            "source": source,
            "source_reference": source_reference,
            "evidence_reality": evidence_reality.value,
            "provenance_verified": provenance_verified,
            "causal_parent_ids": sorted(causal_parent_ids),
            "evidence_ids": sorted(evidence_ids),
            "payload": thaw_json(freeze_json(payload)),
        }
        return cls(
            memory_id=digest_json(semantic),
            kind=kind,
            entity_id=entity_id,
            event_cluster_id=event_cluster_id,
            observed_at=observed_at,
            received_at=received_at,
            recorded_at=recorded_at,
            source=source,
            source_reference=source_reference,
            evidence_reality=evidence_reality,
            provenance_verified=provenance_verified,
            causal_parent_ids=causal_parent_ids,
            evidence_ids=evidence_ids,
            payload=payload,
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": self.kind.value,
            "entity_id": self.entity_id,
            "event_cluster_id": self.event_cluster_id,
            "observed_at": _iso(self.observed_at),
            "received_at": _iso(self.received_at),
            "recorded_at": _iso(self.recorded_at),
            "source": self.source,
            "source_reference": self.source_reference,
            "evidence_reality": self.evidence_reality.value,
            "provenance_verified": self.provenance_verified,
            "causal_parent_ids": list(self.causal_parent_ids),
            "evidence_ids": list(self.evidence_ids),
            "payload": thaw_json(self.payload),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"memory_id": self.memory_id, **self.semantic_dict()}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MemoryRecord:
        return cls(
            memory_id=str(data["memory_id"]),
            kind=MemoryKind(str(data["kind"])),
            entity_id=str(data["entity_id"]),
            event_cluster_id=(
                str(data["event_cluster_id"])
                if data.get("event_cluster_id") is not None
                else None
            ),
            observed_at=_utc(data["observed_at"]),
            received_at=_utc(data["received_at"]),
            recorded_at=_utc(data["recorded_at"]),
            source=str(data["source"]),
            source_reference=str(data["source_reference"]),
            evidence_reality=EvidenceReality(str(data["evidence_reality"])),
            provenance_verified=data.get("provenance_verified") is True,
            causal_parent_ids=tuple(data.get("causal_parent_ids", ())),
            evidence_ids=tuple(data.get("evidence_ids", ())),
            payload=data.get("payload", {}),
        )


__all__ = [
    "EvidenceReality",
    "MemoryKind",
    "MemoryRecord",
    "MemoryValidationError",
]
