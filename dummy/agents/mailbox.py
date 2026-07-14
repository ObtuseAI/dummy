"""Deterministic typed mailbox; free-form agent conversation is forbidden."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Callable

from dummy.agents.lifecycle import AgentState
from dummy.agents.permissions import AgentPermissions, PermissionViolation
from dummy.agents.registry import AgentRegistry, RegistryError
from dummy.protocols import MessageEnvelope


_DELIVERY_NAMESPACE = uuid.UUID("747e1247-786d-57d7-bac0-1557dd7cc7a4")


class MailboxError(ValueError):
    """A mailbox delivery is unknown, duplicated, or unauthorized."""


@dataclass(frozen=True, slots=True)
class MailboxEntry:
    delivery_id: str
    sequence: int
    sender: str
    recipient: str
    message: MessageEnvelope

    def to_dict(self) -> dict[str, object]:
        return {
            "delivery_id": self.delivery_id,
            "sequence": self.sequence,
            "sender": self.sender,
            "recipient": self.recipient,
            "message": self.message.to_dict(),
        }


class DeterministicMailbox:
    def __init__(
        self,
        registry: AgentRegistry,
        *,
        state_lookup: Callable[[str], AgentState],
    ) -> None:
        if not registry.sealed:
            raise MailboxError("mailbox requires a sealed registry")
        self.registry = registry
        self.state_lookup = state_lookup
        self._entries: list[MailboxEntry] = []
        self._delivery_keys: set[tuple[str, str]] = set()

    @property
    def entries(self) -> tuple[MailboxEntry, ...]:
        return tuple(self._entries)

    def publish(
        self,
        *,
        sender: str,
        recipients: tuple[str, ...],
        message: MessageEnvelope,
    ) -> tuple[MailboxEntry, ...]:
        if sender != message.sender:
            raise MailboxError("publisher does not match message sender")
        try:
            sender_contract = self.registry.get(sender)
        except RegistryError as exc:
            raise MailboxError(str(exc)) from exc
        if self.state_lookup(sender) is not AgentState.ACTIVE:
            raise MailboxError(f"sender is not active: {sender}")
        AgentPermissions(sender_contract).assert_output(
            message,
            market_id=message.market_id,
            policy_version=message.policy_version,
        )
        normalized = tuple(sorted(recipients))
        if not normalized:
            raise MailboxError("delivery requires at least one recipient")
        if len(set(normalized)) != len(normalized):
            raise MailboxError("recipient list contains duplicates")

        pending: list[tuple[str, tuple[str, str]]] = []
        for recipient in normalized:
            try:
                contract = self.registry.get(recipient)
            except RegistryError as exc:
                raise MailboxError(str(exc)) from exc
            if self.state_lookup(recipient) is not AgentState.ACTIVE:
                raise MailboxError(f"recipient is not active: {recipient}")
            try:
                AgentPermissions(contract).assert_input(message)
            except PermissionViolation as exc:
                raise MailboxError(str(exc)) from exc
            key = (recipient, message.message_id)
            if key in self._delivery_keys:
                raise MailboxError(
                    f"duplicate delivery for {recipient}: {message.message_id}"
                )
            pending.append((recipient, key))

        delivered: list[MailboxEntry] = []
        for recipient, key in pending:
            sequence = len(self._entries) + 1
            semantic = json.dumps(
                {
                    "sequence": sequence,
                    "sender": sender,
                    "recipient": recipient,
                    "message_id": message.message_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            entry = MailboxEntry(
                delivery_id=str(uuid.uuid5(_DELIVERY_NAMESPACE, semantic)),
                sequence=sequence,
                sender=sender,
                recipient=recipient,
                message=message,
            )
            self._entries.append(entry)
            self._delivery_keys.add(key)
            delivered.append(entry)
        return tuple(delivered)

    def read(
        self,
        recipient: str,
        *,
        after_sequence: int = 0,
    ) -> tuple[MailboxEntry, ...]:
        try:
            self.registry.get(recipient)
        except RegistryError as exc:
            raise MailboxError(str(exc)) from exc
        if after_sequence < 0:
            raise MailboxError("after_sequence cannot be negative")
        return tuple(
            entry
            for entry in self._entries
            if entry.recipient == recipient and entry.sequence > after_sequence
        )
