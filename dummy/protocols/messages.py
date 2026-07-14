"""Immutable, deterministically replayable vNext messages."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from dummy.constitution.authority import Authority


class MessageType(str, Enum):
    OBSERVATION = "OBSERVATION"
    FEATURE = "FEATURE"
    MARKET_STATE = "MARKET_STATE"
    HYPOTHESIS = "HYPOTHESIS"
    FORECAST = "FORECAST"
    COUNTERFORECAST = "COUNTERFORECAST"
    UNCERTAINTY = "UNCERTAINTY"
    DATA_GAP = "DATA_GAP"
    CAUSAL_CLAIM = "CAUSAL_CLAIM"
    CALIBRATION_UPDATE = "CALIBRATION_UPDATE"
    CONTROL_REQUEST = "CONTROL_REQUEST"
    VETO = "VETO"
    SETTLEMENT = "SETTLEMENT"
    FILL_EVIDENCE = "FILL_EVIDENCE"
    HEALTH_ALERT = "HEALTH_ALERT"
    MUTATION_PROPOSAL = "MUTATION_PROPOSAL"


MESSAGE_AUTHORITY = {
    MessageType.OBSERVATION: Authority.OBSERVE,
    MessageType.FEATURE: Authority.MODEL,
    MessageType.MARKET_STATE: Authority.MODEL,
    MessageType.HYPOTHESIS: Authority.MODEL,
    MessageType.FORECAST: Authority.FORECAST,
    MessageType.COUNTERFORECAST: Authority.CHALLENGE,
    MessageType.UNCERTAINTY: Authority.MODEL,
    MessageType.DATA_GAP: Authority.OBSERVE,
    MessageType.CAUSAL_CLAIM: Authority.MODEL,
    MessageType.CALIBRATION_UPDATE: Authority.MODEL,
    MessageType.CONTROL_REQUEST: Authority.RECOMMEND,
    MessageType.VETO: Authority.CHALLENGE,
    MessageType.SETTLEMENT: Authority.OBSERVE,
    MessageType.FILL_EVIDENCE: Authority.OBSERVE,
    MessageType.HEALTH_ALERT: Authority.OBSERVE,
    MessageType.MUTATION_PROPOSAL: Authority.RECOMMEND,
}


def required_authority(message_type: MessageType) -> Authority:
    """Return the exact authority exercised by a message type."""

    return MESSAGE_AUTHORITY[message_type]

MARKET_SCOPED_TYPES = frozenset(
    {
        MessageType.OBSERVATION,
        MessageType.FEATURE,
        MessageType.MARKET_STATE,
        MessageType.HYPOTHESIS,
        MessageType.FORECAST,
        MessageType.COUNTERFORECAST,
        MessageType.UNCERTAINTY,
        MessageType.DATA_GAP,
        MessageType.CAUSAL_CLAIM,
        MessageType.CALIBRATION_UPDATE,
        MessageType.VETO,
        MessageType.SETTLEMENT,
        MessageType.FILL_EVIDENCE,
    }
)

_MESSAGE_NAMESPACE = uuid.UUID("c8b7a09f-193d-58c7-8ef7-3b7394ff7ce7")


class ProtocolValidationError(ValueError):
    """A message violated the typed protocol."""


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProtocolValidationError("timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProtocolValidationError("payload floats must be finite")
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ProtocolValidationError("payload keys must be strings")
        return MappingProxyType(
            {key: _freeze_json(value[key]) for key in sorted(value)}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    raise ProtocolValidationError(f"payload contains non-JSON type: {type(value).__name__}")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_json(data: Mapping[str, Any]) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


@dataclass(frozen=True, slots=True)
class MessageEnvelope:
    message_type: MessageType
    message_id: str
    sender: str
    market_id: str | None
    issued_at: datetime
    effective_time: datetime
    received_at: datetime
    causal_parents: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    model_version: str
    policy_version: str
    authority: Authority
    payload: Mapping[str, Any]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.message_id)
        except (ValueError, AttributeError) as exc:
            raise ProtocolValidationError("message_id must be a UUID") from exc

        for field_name in ("sender", "model_version", "policy_version"):
            if not getattr(self, field_name).strip():
                raise ProtocolValidationError(f"{field_name} must be non-empty")

        if self.message_type in MARKET_SCOPED_TYPES and not (self.market_id or "").strip():
            raise ProtocolValidationError(
                f"{self.message_type.value} requires market_id"
            )

        issued = _parse_time(self.issued_at)
        effective = _parse_time(self.effective_time)
        received = _parse_time(self.received_at)
        if received < issued:
            raise ProtocolValidationError("received_at precedes issued_at")
        object.__setattr__(self, "issued_at", issued)
        object.__setattr__(self, "effective_time", effective)
        object.__setattr__(self, "received_at", received)

        expected_authority = MESSAGE_AUTHORITY[self.message_type]
        if self.authority is not expected_authority:
            raise ProtocolValidationError(
                f"{self.message_type.value} exercises {expected_authority.name}, "
                f"not {self.authority.name}"
            )

        parents = tuple(self.causal_parents)
        evidence = tuple(self.evidence_ids)
        if len(set(parents)) != len(parents):
            raise ProtocolValidationError("causal_parents contains duplicates")
        if len(set(evidence)) != len(evidence):
            raise ProtocolValidationError("evidence_ids contains duplicates")
        if self.message_id in parents:
            raise ProtocolValidationError("message cannot be its own causal parent")
        object.__setattr__(self, "causal_parents", parents)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "limitations", tuple(self.limitations))
        object.__setattr__(self, "payload", _freeze_json(self.payload))

        if self.message_type in {
            MessageType.FORECAST,
            MessageType.COUNTERFORECAST,
        }:
            probability = self.payload.get("probability")
            if (
                not isinstance(probability, (int, float))
                or isinstance(probability, bool)
                or not 0.0 <= float(probability) <= 1.0
            ):
                raise ProtocolValidationError(
                    "forecast payload requires probability in [0, 1]"
                )

    @classmethod
    def create(
        cls,
        *,
        message_type: MessageType,
        sender: str,
        market_id: str | None,
        issued_at: datetime,
        effective_time: datetime,
        received_at: datetime,
        model_version: str,
        policy_version: str,
        payload: Mapping[str, Any],
        causal_parents: tuple[str, ...] = (),
        evidence_ids: tuple[str, ...] = (),
        limitations: tuple[str, ...] = (),
    ) -> MessageEnvelope:
        authority = MESSAGE_AUTHORITY[message_type]
        semantic = {
            "message_type": message_type.value,
            "sender": sender,
            "market_id": market_id,
            "issued_at": _iso(_parse_time(issued_at)),
            "effective_time": _iso(_parse_time(effective_time)),
            "received_at": _iso(_parse_time(received_at)),
            "causal_parents": list(causal_parents),
            "evidence_ids": list(evidence_ids),
            "model_version": model_version,
            "policy_version": policy_version,
            "authority": authority.name,
            "payload": _thaw_json(_freeze_json(payload)),
            "limitations": list(limitations),
        }
        message_id = str(
            uuid.uuid5(_MESSAGE_NAMESPACE, _canonical_json(semantic))
        )
        return cls(
            message_type=message_type,
            message_id=message_id,
            sender=sender,
            market_id=market_id,
            issued_at=issued_at,
            effective_time=effective_time,
            received_at=received_at,
            causal_parents=causal_parents,
            evidence_ids=evidence_ids,
            model_version=model_version,
            policy_version=policy_version,
            authority=authority,
            payload=payload,
            limitations=limitations,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_type": self.message_type.value,
            "message_id": self.message_id,
            "sender": self.sender,
            "market_id": self.market_id,
            "issued_at": _iso(self.issued_at),
            "effective_time": _iso(self.effective_time),
            "received_at": _iso(self.received_at),
            "causal_parents": list(self.causal_parents),
            "evidence_ids": list(self.evidence_ids),
            "model_version": self.model_version,
            "policy_version": self.policy_version,
            "authority": self.authority.name,
            "payload": _thaw_json(self.payload),
            "limitations": list(self.limitations),
        }

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())

    def replay_identity(self) -> str:
        semantic = self.to_dict()
        del semantic["message_id"]
        return hashlib.sha256(_canonical_json(semantic).encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MessageEnvelope:
        """Parse current or legacy envelopes.

        Legacy records may omit received/effective time and limitations; those
        fields default to issued time and an empty list without inventing
        evidence.
        """

        issued_at = _parse_time(data["issued_at"])
        return cls(
            message_type=MessageType(data["message_type"]),
            message_id=str(data["message_id"]),
            sender=str(data["sender"]),
            market_id=(
                str(data["market_id"])
                if data.get("market_id") is not None
                else None
            ),
            issued_at=issued_at,
            effective_time=_parse_time(data.get("effective_time", issued_at)),
            received_at=_parse_time(data.get("received_at", issued_at)),
            causal_parents=tuple(data.get("causal_parents", ())),
            evidence_ids=tuple(data.get("evidence_ids", ())),
            model_version=str(data["model_version"]),
            policy_version=str(data["policy_version"]),
            authority=Authority[str(data["authority"])],
            payload=data.get("payload", {}),
            limitations=tuple(data.get("limitations", ())),
        )
