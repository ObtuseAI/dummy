"""Frozen input context shared by all Phase 5 shadow guards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from dummy.protocols import MessageEnvelope, MessageType

from .models import ShadowValidationError


@dataclass(frozen=True, slots=True)
class GuardContext:
    decision_at: datetime
    state: MessageEnvelope
    messages: tuple[MessageEnvelope, ...]
    resource_usage: Mapping[str, int | float | None]
    resource_budget: Mapping[str, int | float]

    def __post_init__(self) -> None:
        if self.decision_at.tzinfo is None or self.decision_at.utcoffset() is None:
            raise ShadowValidationError("guard decision_at must be timezone-aware")
        decision = self.decision_at.astimezone(timezone.utc)
        if self.state.message_type is not MessageType.MARKET_STATE:
            raise ShadowValidationError("guard context requires one MARKET_STATE")
        messages = tuple(self.messages)
        if not messages:
            raise ShadowValidationError("guard context requires material agent messages")
        state_version = str(self.state.payload.get("state_version", ""))
        if not state_version:
            raise ShadowValidationError("guard state lacks a frozen version")
        for message in messages:
            if message.market_id != self.state.market_id:
                raise ShadowValidationError("guard inputs contain mixed markets")
            if str(message.payload.get("world_state_version", "")) != state_version:
                raise ShadowValidationError("guard inputs contain mixed state versions")
        usage = {str(key): value for key, value in self.resource_usage.items()}
        budget = {str(key): value for key, value in self.resource_budget.items()}
        if any(float(value) < 0.0 for value in usage.values() if value is not None):
            raise ShadowValidationError("resource usage cannot be negative")
        if any(float(value) <= 0.0 for value in budget.values()):
            raise ShadowValidationError("resource budgets must be positive")
        object.__setattr__(self, "decision_at", decision)
        object.__setattr__(self, "messages", messages)
        object.__setattr__(self, "resource_usage", MappingProxyType(usage))
        object.__setattr__(self, "resource_budget", MappingProxyType(budget))

    @property
    def world_state(self) -> Mapping[str, Any]:
        value = self.state.payload.get("world_state", {})
        if not isinstance(value, Mapping):
            raise ShadowValidationError("world state payload is malformed")
        return value

    @property
    def state_version(self) -> str:
        return str(self.state.payload["state_version"])
