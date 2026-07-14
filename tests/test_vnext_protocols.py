from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from dummy.constitution import Authority
from dummy.protocols import MessageEnvelope, MessageType, ProtocolValidationError


NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)


def _forecast(**overrides: object) -> MessageEnvelope:
    values: dict[str, object] = {
        "message_type": MessageType.FORECAST,
        "sender": "btc-15m-incumbent",
        "market_id": "KXBTC15M-26JUL141215",
        "issued_at": NOW,
        "effective_time": NOW,
        "received_at": NOW + timedelta(milliseconds=20),
        "model_version": "model-1",
        "policy_version": "policy-1",
        "payload": {"probability": 0.61, "features": ["momentum", {"lag": 2}]},
        "evidence_ids": ("quote-1",),
        "limitations": ("shadow-only",),
    }
    values.update(overrides)
    return MessageEnvelope.create(**values)  # type: ignore[arg-type]


def test_message_creation_is_deterministic_and_replayable() -> None:
    first = _forecast()
    second = _forecast()
    assert first.message_id == second.message_id
    assert first.to_json() == second.to_json()
    assert first.replay_identity() == second.replay_identity()
    assert MessageEnvelope.from_dict(first.to_dict()) == first


def test_payload_is_deeply_immutable() -> None:
    original = {"probability": 0.61, "nested": {"values": [1, 2]}}
    message = _forecast(payload=original)
    original["probability"] = 0.1
    nested = message.payload["nested"]

    assert isinstance(message.payload, MappingProxyType)
    assert isinstance(nested, MappingProxyType)
    assert message.payload["probability"] == 0.61
    assert nested["values"] == (1, 2)
    with pytest.raises(TypeError):
        message.payload["probability"] = 0.2  # type: ignore[index]


def test_legacy_envelope_defaults_missing_optional_time_fields() -> None:
    current = _forecast().to_dict()
    current.pop("effective_time")
    current.pop("received_at")
    current.pop("limitations")

    parsed = MessageEnvelope.from_dict(current)
    assert parsed.effective_time == parsed.issued_at
    assert parsed.received_at == parsed.issued_at
    assert parsed.limitations == ()


def test_message_type_exercises_exact_authority() -> None:
    data = _forecast().to_dict()
    data["authority"] = Authority.EXECUTE.name
    with pytest.raises(ProtocolValidationError, match="FORECAST exercises FORECAST"):
        MessageEnvelope.from_dict(data)


@pytest.mark.parametrize(
    "message_type",
    [MessageType.OBSERVATION, MessageType.FORECAST, MessageType.SETTLEMENT],
)
def test_market_scoped_messages_require_market_id(message_type: MessageType) -> None:
    payload = {"probability": 0.5} if message_type is MessageType.FORECAST else {}
    with pytest.raises(ProtocolValidationError, match="requires market_id"):
        MessageEnvelope.create(
            message_type=message_type,
            sender="agent",
            market_id=None,
            issued_at=NOW,
            effective_time=NOW,
            received_at=NOW,
            model_version="v1",
            policy_version="v1",
            payload=payload,
        )


@pytest.mark.parametrize("probability", [-0.01, 1.01, float("nan"), True, "0.5", None])
def test_forecast_probability_is_strictly_validated(probability: object) -> None:
    with pytest.raises(ProtocolValidationError):
        _forecast(payload={"probability": probability})


def test_timestamps_must_be_aware_and_causally_receivable() -> None:
    with pytest.raises(ProtocolValidationError, match="timezone-aware"):
        _forecast(issued_at=NOW.replace(tzinfo=None))
    with pytest.raises(ProtocolValidationError, match="precedes issued_at"):
        _forecast(received_at=NOW - timedelta(microseconds=1))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("causal_parents", ("same", "same"), "causal_parents contains duplicates"),
        ("evidence_ids", ("same", "same"), "evidence_ids contains duplicates"),
    ],
)
def test_evidence_identifiers_must_be_unique(
    field: str,
    value: tuple[str, ...],
    message: str,
) -> None:
    with pytest.raises(ProtocolValidationError, match=message):
        _forecast(**{field: value})


def test_message_cannot_parent_itself() -> None:
    message = _forecast()
    data = message.to_dict()
    data["causal_parents"] = [message.message_id]
    with pytest.raises(ProtocolValidationError, match="own causal parent"):
        MessageEnvelope.from_dict(data)
