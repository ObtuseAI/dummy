"""Authority and message permissions derived from an agent contract."""

from __future__ import annotations

from dataclasses import dataclass

from dummy.agents.contract import AgentContract
from dummy.protocols import MessageEnvelope, MessageType, required_authority


class PermissionViolation(PermissionError):
    """An agent attempted an undeclared input or output action."""


@dataclass(frozen=True, slots=True)
class AgentPermissions:
    contract: AgentContract

    def can_receive(self, message_type: MessageType) -> bool:
        return message_type in self.contract.input_types

    def can_emit(self, message_type: MessageType) -> bool:
        return (
            message_type in self.contract.output_types
            and required_authority(message_type) <= self.contract.authority
        )

    def missing_evidence(self, available: tuple[str, ...]) -> tuple[str, ...]:
        provided = set(available)
        return tuple(
            item
            for item in self.contract.evidence_requirements
            if item not in provided
        )

    def assert_input(self, message: MessageEnvelope) -> None:
        if not self.can_receive(message.message_type):
            raise PermissionViolation(
                f"{self.contract.agent_id} cannot receive {message.message_type.value}"
            )

    def assert_output(
        self,
        message: MessageEnvelope,
        *,
        market_id: str | None,
        policy_version: str,
    ) -> None:
        if message.sender != self.contract.agent_id:
            raise PermissionViolation("message sender does not match agent contract")
        if not self.can_emit(message.message_type):
            raise PermissionViolation(
                f"{self.contract.agent_id} cannot emit {message.message_type.value}"
            )
        if message.market_id != market_id:
            raise PermissionViolation("output market_id differs from invocation")
        if message.policy_version != policy_version:
            raise PermissionViolation("output policy_version differs from invocation")
