"""Immutable, causally versioned world-state contracts for DUMMY vNext."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from dummy import VNEXT_MATURITY


_FIELD_KEY = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")


class WorldModelValidationError(ValueError):
    """A world-model contract or value is incomplete, unsafe, or noncausal."""


class WorldHydrationError(WorldModelValidationError):
    """Required world state could not be frozen without guessing."""


class WorldStateStaleError(WorldModelValidationError):
    """A frozen snapshot's lease expired before consumption."""


class WorldDomain(str, Enum):
    CRYPTO = "crypto"
    MLB = "mlb"
    NBA = "nba"
    NFL = "nfl"
    NCAAF = "ncaaf"
    NHL = "nhl"
    NCAAMB = "ncaamb"


class StateLayer(str, Enum):
    FACT = "fact"
    DERIVED = "derived"
    HYPOTHESIS = "hypothesis"
    MISSING = "missing"


class ValueStatus(str, Enum):
    PRESENT = "present"
    MISSING = "missing"
    STALE = "stale"
    CONTRADICTED = "contradicted"


class MissingDataPolicy(str, Enum):
    ABSTAIN = "abstain"
    EXPLICIT_UNKNOWN = "explicit_unknown"
    EXCLUDE = "exclude"
    WIDEN_UNCERTAINTY = "widen_uncertainty"


class ContradictionSeverity(str, Enum):
    INFORMATIONAL = "informational"
    WARNING = "warning"
    BLOCKING = "blocking"


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise WorldModelValidationError("world-model timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return utc(value).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return utc(value)
    try:
        return utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError as exc:
        raise WorldModelValidationError("invalid world-model timestamp") from exc


def freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WorldModelValidationError("world-state floats must be finite")
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise WorldModelValidationError("world-state keys must be strings")
        return MappingProxyType(
            {key: freeze_json(value[key]) for key in sorted(value)}
        )
    if isinstance(value, (tuple, list)):
        return tuple(freeze_json(item) for item in value)
    raise WorldModelValidationError(
        f"world state contains non-JSON type: {type(value).__name__}"
    )


def thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        thaw_json(freeze_json(value)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest_json(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def bounded(value: float, *, name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        raise WorldModelValidationError(f"{name} must be in [0, 1]")
    return parsed


def unique(values: tuple[str, ...], *, name: str, allow_empty: bool = True) -> tuple[str, ...]:
    normalized = tuple(sorted(item.strip() for item in values))
    if (not allow_empty and not normalized) or any(not item for item in normalized):
        raise WorldModelValidationError(f"{name} contains an empty value")
    if len(set(normalized)) != len(normalized):
        raise WorldModelValidationError(f"{name} contains duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class WorldFieldSpec:
    key: str
    description: str
    unit: str
    critical: bool
    lease_ms: int
    allowed_layers: tuple[StateLayer, ...]
    missing_policy: MissingDataPolicy

    def __post_init__(self) -> None:
        if not _FIELD_KEY.fullmatch(self.key):
            raise WorldModelValidationError(f"invalid world field key: {self.key!r}")
        if not self.description.strip() or not self.unit.strip():
            raise WorldModelValidationError("world field description and unit are required")
        if self.lease_ms <= 0:
            raise WorldModelValidationError("world field lease_ms must be positive")
        layers = tuple(sorted(set(self.allowed_layers), key=lambda item: item.value))
        if not layers or StateLayer.MISSING in layers:
            raise WorldModelValidationError(
                "field allowed_layers must contain non-missing layers"
            )
        if self.critical and self.missing_policy is not MissingDataPolicy.ABSTAIN:
            raise WorldModelValidationError("critical fields must fail closed with ABSTAIN")
        object.__setattr__(self, "allowed_layers", layers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "description": self.description,
            "unit": self.unit,
            "critical": self.critical,
            "lease_ms": self.lease_ms,
            "allowed_layers": [item.value for item in self.allowed_layers],
            "missing_policy": self.missing_policy.value,
        }


@dataclass(frozen=True, slots=True)
class WorldStateSchema:
    schema_id: str
    schema_version: str
    domain: WorldDomain
    scope: str
    fields: tuple[WorldFieldSpec, ...]

    def __post_init__(self) -> None:
        if not self.schema_id.strip() or not self.schema_version.strip():
            raise WorldModelValidationError("schema identity and version are required")
        if not self.scope.strip():
            raise WorldModelValidationError("schema scope is required")
        fields = tuple(sorted(self.fields, key=lambda item: item.key))
        if not fields:
            raise WorldModelValidationError("world schema requires fields")
        keys = tuple(item.key for item in fields)
        if len(set(keys)) != len(keys):
            raise WorldModelValidationError("world schema contains duplicate field keys")
        if not any(item.critical for item in fields):
            raise WorldModelValidationError("world schema requires a critical field")
        object.__setattr__(self, "fields", fields)

    def field(self, key: str) -> WorldFieldSpec:
        matches = tuple(item for item in self.fields if item.key == key)
        if len(matches) != 1:
            raise WorldModelValidationError(f"unknown world field: {key}")
        return matches[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "domain": self.domain.value,
            "scope": self.scope,
            "fields": [item.to_dict() for item in self.fields],
        }

    def digest(self) -> str:
        return digest_json(self.to_dict())


@dataclass(frozen=True, slots=True)
class WorldObservation:
    field_key: str
    layer: StateLayer
    value: Any
    unit: str
    uncertainty: float
    observed_at: datetime
    received_at: datetime
    timestamp_verified: bool
    source: str
    source_family: str
    source_reference: str
    evidence_id: str
    revision_id: str
    supersedes_revision_id: str | None = None
    transform_version: str = "raw-v1"
    causal_evidence_ids: tuple[str, ...] = ()
    probability: float | None = None
    calibration_identity: str | None = None
    mapping_evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _FIELD_KEY.fullmatch(self.field_key):
            raise WorldModelValidationError(f"invalid observation field: {self.field_key!r}")
        if self.layer is StateLayer.MISSING:
            raise WorldModelValidationError("observations cannot use MISSING layer")
        for field_name in (
            "unit",
            "source",
            "source_family",
            "source_reference",
            "evidence_id",
            "revision_id",
            "transform_version",
        ):
            if not str(getattr(self, field_name)).strip():
                raise WorldModelValidationError(f"{field_name} must be non-empty")
        observed = utc(self.observed_at)
        received = utc(self.received_at)
        if observed > received:
            raise WorldModelValidationError("world observation occurs after receipt")
        if not self.timestamp_verified:
            raise WorldModelValidationError(
                "unverified provider timestamp cannot enter world state"
            )
        if self.supersedes_revision_id is not None and not self.supersedes_revision_id.strip():
            raise WorldModelValidationError("supersedes_revision_id cannot be blank")
        uncertainty = bounded(self.uncertainty, name="uncertainty")
        causal = unique(self.causal_evidence_ids, name="causal_evidence_ids")
        mapping = unique(self.mapping_evidence_ids, name="mapping_evidence_ids")
        limitations = unique(self.limitations, name="limitations")
        probability = self.probability
        if self.layer is StateLayer.FACT:
            if causal or mapping or probability is not None or self.calibration_identity:
                raise WorldModelValidationError(
                    "raw facts cannot declare transforms or probabilistic mappings"
                )
        elif self.layer is StateLayer.DERIVED:
            if not causal:
                raise WorldModelValidationError("derived state requires causal evidence")
            if mapping or probability is not None or self.calibration_identity:
                raise WorldModelValidationError(
                    "derived state cannot masquerade as a probabilistic hypothesis"
                )
        elif self.layer is StateLayer.HYPOTHESIS:
            if not causal:
                raise WorldModelValidationError("hypothesis requires causal evidence")
            if probability is None:
                raise WorldModelValidationError("hypothesis requires probability")
            probability = bounded(probability, name="probability")
            if not (self.calibration_identity or "").strip() or not mapping:
                raise WorldModelValidationError(
                    "hypothesis requires calibration identity and mapping evidence"
                )
        object.__setattr__(self, "value", freeze_json(self.value))
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "received_at", received)
        object.__setattr__(self, "uncertainty", uncertainty)
        object.__setattr__(self, "probability", probability)
        object.__setattr__(self, "causal_evidence_ids", causal)
        object.__setattr__(self, "mapping_evidence_ids", mapping)
        object.__setattr__(self, "limitations", limitations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_key": self.field_key,
            "layer": self.layer.value,
            "value": thaw_json(self.value),
            "unit": self.unit,
            "uncertainty": self.uncertainty,
            "observed_at": iso(self.observed_at),
            "received_at": iso(self.received_at),
            "timestamp_verified": self.timestamp_verified,
            "source": self.source,
            "source_family": self.source_family,
            "source_reference": self.source_reference,
            "evidence_id": self.evidence_id,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "transform_version": self.transform_version,
            "causal_evidence_ids": list(self.causal_evidence_ids),
            "probability": self.probability,
            "calibration_identity": self.calibration_identity,
            "mapping_evidence_ids": list(self.mapping_evidence_ids),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    source: str
    source_family: str
    source_reference: str
    evidence_id: str
    revision_id: str
    observed_at: datetime
    received_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "source",
            "source_family",
            "source_reference",
            "evidence_id",
            "revision_id",
        ):
            if not getattr(self, field_name).strip():
                raise WorldModelValidationError(f"{field_name} must be non-empty")
        object.__setattr__(self, "observed_at", utc(self.observed_at))
        object.__setattr__(self, "received_at", utc(self.received_at))

    @classmethod
    def from_observation(cls, observation: WorldObservation) -> ProvenanceRecord:
        return cls(
            source=observation.source,
            source_family=observation.source_family,
            source_reference=observation.source_reference,
            evidence_id=observation.evidence_id,
            revision_id=observation.revision_id,
            observed_at=observation.observed_at,
            received_at=observation.received_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_family": self.source_family,
            "source_reference": self.source_reference,
            "evidence_id": self.evidence_id,
            "revision_id": self.revision_id,
            "observed_at": iso(self.observed_at),
            "received_at": iso(self.received_at),
        }


@dataclass(frozen=True, slots=True)
class WorldStateValue:
    field_key: str
    layer: StateLayer
    status: ValueStatus
    value: Any
    unit: str
    uncertainty: float
    probability: float | None
    observed_at: datetime | None
    received_at: datetime | None
    valid_until: datetime | None
    provenance: tuple[ProvenanceRecord, ...]
    transform_version: str
    causal_evidence_ids: tuple[str, ...]
    calibration_identity: str | None
    mapping_evidence_ids: tuple[str, ...]
    missing_reason: str | None
    missing_policy: MissingDataPolicy
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _FIELD_KEY.fullmatch(self.field_key):
            raise WorldModelValidationError(f"invalid state field: {self.field_key!r}")
        if not self.unit.strip() or not self.transform_version.strip():
            raise WorldModelValidationError("state unit and transform version are required")
        uncertainty = bounded(self.uncertainty, name="state uncertainty")
        causal = unique(self.causal_evidence_ids, name="state causal evidence")
        mapping = unique(self.mapping_evidence_ids, name="state mapping evidence")
        limitations = unique(self.limitations, name="state limitations")
        provenance = tuple(
            sorted(self.provenance, key=lambda item: (item.received_at, item.evidence_id))
        )
        if self.status is ValueStatus.PRESENT:
            if self.layer is StateLayer.MISSING or self.value is None:
                raise WorldModelValidationError("present state requires non-missing value")
            if self.observed_at is None or self.received_at is None or self.valid_until is None:
                raise WorldModelValidationError("present state requires causal timestamps")
            observed = utc(self.observed_at)
            received = utc(self.received_at)
            valid_until = utc(self.valid_until)
            if not observed <= received <= valid_until:
                raise WorldModelValidationError("state lease violates causal order")
            if not provenance:
                raise WorldModelValidationError("present state requires provenance")
        else:
            if self.layer is not StateLayer.MISSING or self.value is not None:
                raise WorldModelValidationError("non-present state must be explicit MISSING")
            if provenance:
                raise WorldModelValidationError(
                    "missing state cannot claim observation provenance"
                )
            if not (self.missing_reason or "").strip():
                raise WorldModelValidationError("missing state requires a reason")
            if uncertainty != 1.0 or self.probability is not None:
                raise WorldModelValidationError(
                    "missing state must carry maximum uncertainty and no probability"
                )
            observed = None
            received = None
            valid_until = None
        if self.layer is StateLayer.HYPOTHESIS:
            if self.probability is None or not self.calibration_identity or not mapping:
                raise WorldModelValidationError("hypothesis state lacks mapping identity")
            bounded(self.probability, name="state probability")
        elif self.probability is not None:
            raise WorldModelValidationError("non-hypothesis state cannot carry probability")
        object.__setattr__(self, "value", freeze_json(self.value))
        object.__setattr__(self, "uncertainty", uncertainty)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "received_at", received)
        object.__setattr__(self, "valid_until", valid_until)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "causal_evidence_ids", causal)
        object.__setattr__(self, "mapping_evidence_ids", mapping)
        object.__setattr__(self, "limitations", limitations)

    @classmethod
    def missing(
        cls,
        spec: WorldFieldSpec,
        *,
        status: ValueStatus,
        reason: str,
        limitations: tuple[str, ...] = (),
    ) -> WorldStateValue:
        if status is ValueStatus.PRESENT:
            raise WorldModelValidationError("missing constructor requires non-present status")
        return cls(
            field_key=spec.key,
            layer=StateLayer.MISSING,
            status=status,
            value=None,
            unit=spec.unit,
            uncertainty=1.0,
            probability=None,
            observed_at=None,
            received_at=None,
            valid_until=None,
            provenance=(),
            transform_version="missing-state-v1",
            causal_evidence_ids=(),
            calibration_identity=None,
            mapping_evidence_ids=(),
            missing_reason=reason,
            missing_policy=spec.missing_policy,
            limitations=limitations,
        )

    @classmethod
    def from_observations(
        cls,
        spec: WorldFieldSpec,
        observations: tuple[WorldObservation, ...],
    ) -> WorldStateValue:
        if not observations:
            raise WorldModelValidationError("state value requires observations")
        selected = max(observations, key=lambda item: (item.received_at, item.revision_id))
        return cls(
            field_key=spec.key,
            layer=selected.layer,
            status=ValueStatus.PRESENT,
            value=thaw_json(selected.value),
            unit=spec.unit,
            uncertainty=max(item.uncertainty for item in observations),
            probability=selected.probability,
            observed_at=selected.observed_at,
            received_at=selected.received_at,
            valid_until=selected.received_at + timedelta(milliseconds=spec.lease_ms),
            provenance=tuple(ProvenanceRecord.from_observation(item) for item in observations),
            transform_version=selected.transform_version,
            causal_evidence_ids=selected.causal_evidence_ids,
            calibration_identity=selected.calibration_identity,
            mapping_evidence_ids=selected.mapping_evidence_ids,
            missing_reason=None,
            missing_policy=spec.missing_policy,
            limitations=tuple(
                sorted({item for observation in observations for item in observation.limitations})
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_key": self.field_key,
            "layer": self.layer.value,
            "status": self.status.value,
            "value": thaw_json(self.value),
            "unit": self.unit,
            "uncertainty": self.uncertainty,
            "probability": self.probability,
            "observed_at": iso(self.observed_at) if self.observed_at else None,
            "received_at": iso(self.received_at) if self.received_at else None,
            "valid_until": iso(self.valid_until) if self.valid_until else None,
            "provenance": [item.to_dict() for item in self.provenance],
            "provenance_status": (
                "verified_observation_chain"
                if self.provenance
                else "no_verified_observation"
            ),
            "transform_version": self.transform_version,
            "causal_evidence_ids": list(self.causal_evidence_ids),
            "calibration_identity": self.calibration_identity,
            "mapping_evidence_ids": list(self.mapping_evidence_ids),
            "missing_reason": self.missing_reason,
            "missing_policy": self.missing_policy.value,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class WorldContradiction:
    contradiction_id: str
    field_keys: tuple[str, ...]
    severity: ContradictionSeverity
    reason: str
    evidence_ids: tuple[str, ...]
    resolved: bool = False
    resolution_evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.contradiction_id.strip() or not self.reason.strip():
            raise WorldModelValidationError("contradiction identity and reason are required")
        fields = unique(self.field_keys, name="contradiction field_keys", allow_empty=False)
        evidence = unique(self.evidence_ids, name="contradiction evidence_ids", allow_empty=False)
        resolution = unique(
            self.resolution_evidence_ids,
            name="resolution_evidence_ids",
        )
        if self.resolved and not resolution:
            raise WorldModelValidationError("resolved contradiction requires evidence")
        if not self.resolved and resolution:
            raise WorldModelValidationError("unresolved contradiction cannot have resolution evidence")
        object.__setattr__(self, "field_keys", fields)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "resolution_evidence_ids", resolution)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contradiction_id": self.contradiction_id,
            "field_keys": list(self.field_keys),
            "severity": self.severity.value,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "resolved": self.resolved,
            "resolution_evidence_ids": list(self.resolution_evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class WorldStateSnapshot:
    snapshot_id: str
    schema: WorldStateSchema
    market_id: str
    as_of: datetime
    policy_version: str
    values: tuple[WorldStateValue, ...]
    contradictions: tuple[WorldContradiction, ...]
    source_observation_digest: str
    maturity: str = VNEXT_MATURITY
    frozen: bool = True

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip() or not self.market_id.strip():
            raise WorldModelValidationError("snapshot and market identity are required")
        if not self.policy_version.strip():
            raise WorldModelValidationError("snapshot policy_version is required")
        if not self.source_observation_digest.strip():
            raise WorldModelValidationError(
                "snapshot source_observation_digest is required"
            )
        if self.maturity != VNEXT_MATURITY or not self.frozen:
            raise WorldModelValidationError("world snapshot must be frozen and experimental")
        as_of = utc(self.as_of)
        values = tuple(sorted(self.values, key=lambda item: item.field_key))
        if tuple(item.field_key for item in values) != tuple(
            item.key for item in self.schema.fields
        ):
            raise WorldModelValidationError("snapshot values do not exactly match schema")
        if any(item.received_at and item.received_at > as_of for item in values):
            raise WorldModelValidationError("future-received state entered snapshot")
        contradictions = tuple(
            sorted(self.contradictions, key=lambda item: item.contradiction_id)
        )
        if any(
            item.severity is ContradictionSeverity.BLOCKING and not item.resolved
            for item in contradictions
        ):
            raise WorldHydrationError("snapshot contains unresolved blocking contradiction")
        critical_missing = tuple(
            spec.key
            for spec, value in zip(self.schema.fields, values, strict=True)
            if spec.critical and value.status is not ValueStatus.PRESENT
        )
        if critical_missing:
            raise WorldHydrationError(f"critical world state is missing: {critical_missing}")
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "contradictions", contradictions)
        expected_id = self.identity_for(
            schema=self.schema,
            market_id=self.market_id,
            as_of=as_of,
            policy_version=self.policy_version,
            values=values,
            contradictions=contradictions,
            source_observation_digest=self.source_observation_digest,
        )
        if self.snapshot_id != expected_id:
            raise WorldModelValidationError(
                "snapshot_id does not match immutable world-state contents"
            )

    @staticmethod
    def identity_for(
        *,
        schema: WorldStateSchema,
        market_id: str,
        as_of: datetime,
        policy_version: str,
        values: tuple[WorldStateValue, ...],
        contradictions: tuple[WorldContradiction, ...],
        source_observation_digest: str,
    ) -> str:
        """Return the content identity without recursively hashing the identity."""

        return digest_json(
            {
                "schema_digest": schema.digest(),
                "market_id": market_id,
                "as_of": iso(as_of),
                "policy_version": policy_version,
                "values": [
                    item.to_dict()
                    for item in sorted(values, key=lambda value: value.field_key)
                ],
                "contradictions": [
                    item.to_dict()
                    for item in sorted(
                        contradictions,
                        key=lambda contradiction: contradiction.contradiction_id,
                    )
                ],
                "source_observation_digest": source_observation_digest,
                "maturity": VNEXT_MATURITY,
                "frozen": True,
            }
        )

    @property
    def completeness(self) -> float:
        present = sum(item.status is ValueStatus.PRESENT for item in self.values)
        return round(present / len(self.values), 12)

    @property
    def valid_until(self) -> datetime:
        critical = tuple(
            value.valid_until
            for spec, value in zip(self.schema.fields, self.values, strict=True)
            if spec.critical and value.valid_until is not None
        )
        if not critical:
            raise WorldHydrationError("snapshot has no critical lease")
        return min(critical)

    def assert_usable(self, at: datetime) -> None:
        when = utc(at)
        if when > self.valid_until:
            raise WorldStateStaleError(
                f"world snapshot expired at {iso(self.valid_until)}"
            )

    def value(self, key: str) -> WorldStateValue:
        matches = tuple(item for item in self.values if item.field_key == key)
        if len(matches) != 1:
            raise WorldModelValidationError(f"unknown snapshot field: {key}")
        return matches[0]

    def to_dict(self) -> dict[str, Any]:
        grouped = {
            layer.value: [
                item.to_dict() for item in self.values if item.layer is layer
            ]
            for layer in StateLayer
        }
        return {
            "snapshot_id": self.snapshot_id,
            "schema": self.schema.to_dict(),
            "schema_digest": self.schema.digest(),
            "market_id": self.market_id,
            "as_of": iso(self.as_of),
            "valid_until": iso(self.valid_until),
            "policy_version": self.policy_version,
            "maturity": self.maturity,
            "frozen": self.frozen,
            "completeness": self.completeness,
            "source_observation_digest": self.source_observation_digest,
            "values": [item.to_dict() for item in self.values],
            "layers": grouped,
            "contradictions": [item.to_dict() for item in self.contradictions],
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def digest(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()
