"""Fail-closed deterministic invocation runtime for registered agents."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, runtime_checkable

from dummy.agents.contract import AgentContract
from dummy.agents.health import AgentHealth, HealthPolicy, HealthStatus
from dummy.agents.lifecycle import AgentLifecycle, AgentState
from dummy.agents.mailbox import DeterministicMailbox
from dummy.agents.permissions import AgentPermissions, PermissionViolation
from dummy.agents.registry import AgentRegistry, RegistryError
from dummy.chronos import ClockDomain
from dummy.protocols import MessageEnvelope


_INVOCATION_NAMESPACE = uuid.UUID("6f82157f-84bc-58c0-9c54-fc92541a4381")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("invocation timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class InvocationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    ABSTAINED = "ABSTAINED"
    DENIED = "DENIED"
    DEGRADED = "DEGRADED"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True, slots=True)
class AgentInvocation:
    invocation_id: str
    agent_id: str
    market_id: str | None
    market_type: str
    clock_domain: ClockDomain
    policy_version: str
    invoked_at: datetime
    evidence_keys: tuple[str, ...]
    input_messages: tuple[MessageEnvelope, ...]

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.invocation_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("invocation_id must be a UUID") from exc
        if not self.agent_id.strip() or not self.market_type.strip():
            raise ValueError("agent_id and market_type must be non-empty")
        if not self.policy_version.strip():
            raise ValueError("policy_version must be non-empty")
        object.__setattr__(self, "invoked_at", _utc(self.invoked_at))
        evidence = tuple(sorted(self.evidence_keys))
        if any(not item.strip() for item in evidence):
            raise ValueError("evidence_keys contains an empty value")
        if len(set(evidence)) != len(evidence):
            raise ValueError("evidence_keys contains duplicates")
        object.__setattr__(self, "evidence_keys", evidence)
        object.__setattr__(self, "input_messages", tuple(self.input_messages))

    @classmethod
    def create(
        cls,
        *,
        agent_id: str,
        market_id: str | None,
        market_type: str,
        clock_domain: ClockDomain,
        policy_version: str,
        invoked_at: datetime,
        evidence_keys: tuple[str, ...],
        input_messages: tuple[MessageEnvelope, ...],
    ) -> AgentInvocation:
        when = _utc(invoked_at)
        semantic = json.dumps(
            {
                "agent_id": agent_id,
                "market_id": market_id,
                "market_type": market_type,
                "clock_domain": clock_domain.value,
                "policy_version": policy_version,
                "invoked_at": when.isoformat(),
                "evidence_keys": sorted(evidence_keys),
                "input_replay_ids": [
                    message.replay_identity() for message in input_messages
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return cls(
            invocation_id=str(uuid.uuid5(_INVOCATION_NAMESPACE, semantic)),
            agent_id=agent_id,
            market_id=market_id,
            market_type=market_type,
            clock_domain=clock_domain,
            policy_version=policy_version,
            invoked_at=when,
            evidence_keys=evidence_keys,
            input_messages=input_messages,
        )


@runtime_checkable
class AgentHandler(Protocol):
    def __call__(
        self,
        invocation: AgentInvocation,
    ) -> MessageEnvelope | tuple[MessageEnvelope, ...] | None: ...


@dataclass(frozen=True, slots=True)
class InvocationResult:
    invocation_id: str
    agent_id: str
    status: InvocationStatus
    outputs: tuple[MessageEnvelope, ...]
    reasons: tuple[str, ...]
    lifecycle_state: AgentState


class AgentRuntime:
    def __init__(self, health_policy: HealthPolicy | None = None) -> None:
        self.registry = AgentRegistry()
        self.health_policy = health_policy or HealthPolicy()
        self._handlers: dict[str, AgentHandler] = {}
        self._lifecycles: dict[str, AgentLifecycle] = {}
        self._failures: dict[str, int] = {}
        self._invalid_outputs: dict[str, int] = {}
        self._last_success: dict[str, datetime | None] = {}
        self._last_failure: dict[str, datetime | None] = {}
        self._mailbox: DeterministicMailbox | None = None

    def register(self, contract: AgentContract, handler: AgentHandler) -> None:
        if not callable(handler):
            raise TypeError("agent handler must be callable")
        self.registry.register(contract)
        self._handlers[contract.agent_id] = handler

    def seal(self) -> tuple[str, ...]:
        order = self.registry.seal()
        for agent_id in order:
            self._lifecycles[agent_id] = AgentLifecycle(agent_id)
            self._failures[agent_id] = 0
            self._invalid_outputs[agent_id] = 0
            self._last_success[agent_id] = None
            self._last_failure[agent_id] = None
        self._mailbox = DeterministicMailbox(
            self.registry,
            state_lookup=lambda agent_id: self.lifecycle(agent_id).state,
        )
        return order

    def lifecycle(self, agent_id: str) -> AgentLifecycle:
        try:
            return self._lifecycles[agent_id]
        except KeyError as exc:
            raise RegistryError("runtime must be sealed before lifecycle access") from exc

    def mailbox(self) -> DeterministicMailbox:
        if not self.registry.sealed:
            raise RegistryError("runtime must be sealed before mailbox access")
        if self._mailbox is None:
            raise RegistryError("runtime mailbox is unavailable")
        return self._mailbox

    def activate(self, agent_id: str, *, at: datetime) -> None:
        contract = self.registry.get(agent_id)
        inactive_dependencies = tuple(
            dependency
            for dependency in contract.dependencies
            if self.lifecycle(dependency).state is not AgentState.ACTIVE
        )
        if inactive_dependencies:
            raise RegistryError(
                f"inactive dependencies for {agent_id}: {inactive_dependencies}"
            )
        lifecycle = self.lifecycle(agent_id)
        lifecycle.transition(AgentState.WARMING, at=at, reason="runtime_warmup")
        lifecycle.transition(AgentState.READY, at=at, reason="contract_ready")
        lifecycle.transition(AgentState.ACTIVE, at=at, reason="runtime_activation")

    def recover(
        self,
        agent_id: str,
        *,
        at: datetime,
        review_authorized: bool = False,
        review_evidence_ids: tuple[str, ...] = (),
    ) -> None:
        contract = self.registry.get(agent_id)
        inactive_dependencies = tuple(
            dependency
            for dependency in contract.dependencies
            if self.lifecycle(dependency).state is not AgentState.ACTIVE
        )
        if inactive_dependencies:
            raise RegistryError(
                f"inactive dependencies for {agent_id}: {inactive_dependencies}"
            )
        lifecycle = self.lifecycle(agent_id)
        was_quarantined = lifecycle.state is AgentState.QUARANTINED
        lifecycle.transition(
            AgentState.WARMING,
            at=at,
            reason="health_recovery",
            evidence_ids=review_evidence_ids,
            review_authorized=review_authorized,
        )
        lifecycle.transition(AgentState.READY, at=at, reason="recovery_ready")
        lifecycle.transition(AgentState.ACTIVE, at=at, reason="recovery_activation")
        self._last_success[agent_id] = None
        self._failures[agent_id] = 0
        if was_quarantined:
            self._invalid_outputs[agent_id] = 0

    def _result(
        self,
        invocation: AgentInvocation,
        status: InvocationStatus,
        *,
        outputs: tuple[MessageEnvelope, ...] = (),
        reasons: tuple[str, ...] = (),
    ) -> InvocationResult:
        return InvocationResult(
            invocation_id=invocation.invocation_id,
            agent_id=invocation.agent_id,
            status=status,
            outputs=outputs,
            reasons=reasons,
            lifecycle_state=self.lifecycle(invocation.agent_id).state,
        )

    def _abstain(
        self,
        invocation: AgentInvocation,
        reason: str,
    ) -> InvocationResult:
        lifecycle = self.lifecycle(invocation.agent_id)
        lifecycle.transition(
            AgentState.ABSTAINING,
            at=invocation.invoked_at,
            reason=reason,
        )
        return self._result(
            invocation,
            InvocationStatus.ABSTAINED,
            reasons=(reason,),
        )

    def _degrade(
        self,
        invocation: AgentInvocation,
        reason: str,
        *,
        invalid_output: bool,
    ) -> InvocationResult:
        agent_id = invocation.agent_id
        self._failures[agent_id] += 1
        if invalid_output:
            self._invalid_outputs[agent_id] += 1
        self._last_failure[agent_id] = invocation.invoked_at
        health = self.health(agent_id, now=invocation.invoked_at)
        target = (
            AgentState.QUARANTINED
            if health.status is HealthStatus.QUARANTINED
            else AgentState.DEGRADED
        )
        self.lifecycle(agent_id).transition(
            target,
            at=invocation.invoked_at,
            reason=reason,
            evidence_ids=(invocation.invocation_id,),
        )
        status = (
            InvocationStatus.QUARANTINED
            if target is AgentState.QUARANTINED
            else InvocationStatus.DEGRADED
        )
        return self._result(invocation, status, reasons=(reason,))

    def invoke(self, invocation: AgentInvocation) -> InvocationResult:
        contract = self.registry.get(invocation.agent_id)
        lifecycle = self.lifecycle(invocation.agent_id)
        if lifecycle.state is not AgentState.ACTIVE:
            return self._result(
                invocation,
                InvocationStatus.DENIED,
                reasons=(f"agent_not_active:{lifecycle.state.value}",),
            )
        current_health = self.health(invocation.agent_id, now=invocation.invoked_at)
        if current_health.status is HealthStatus.ABSTAINING:
            return self._abstain(invocation, "health_abstention")
        if current_health.status in {
            HealthStatus.DEGRADED,
            HealthStatus.QUARANTINED,
        }:
            target = (
                AgentState.QUARANTINED
                if current_health.status is HealthStatus.QUARANTINED
                else AgentState.DEGRADED
            )
            lifecycle.transition(
                target,
                at=invocation.invoked_at,
                reason="health_gate",
                evidence_ids=(invocation.invocation_id,),
            )
            status = (
                InvocationStatus.QUARANTINED
                if target is AgentState.QUARANTINED
                else InvocationStatus.DEGRADED
            )
            return self._result(
                invocation,
                status,
                reasons=("health_gate",),
            )
        if invocation.clock_domain is not contract.clock_domain:
            return self._abstain(invocation, "clock_domain_mismatch")
        if not contract.supports_market_type(invocation.market_type):
            return self._abstain(invocation, "unsupported_market_type")
        if len(invocation.input_messages) > contract.budget.max_messages_per_invocation:
            return self._degrade(
                invocation,
                "input_message_budget_exceeded",
                invalid_output=False,
            )
        if len(invocation.evidence_keys) > contract.budget.max_evidence_items:
            return self._degrade(
                invocation,
                "evidence_budget_exceeded",
                invalid_output=False,
            )

        permissions = AgentPermissions(contract)
        missing = permissions.missing_evidence(invocation.evidence_keys)
        if missing:
            return self._abstain(
                invocation,
                f"missing_evidence:{','.join(missing)}",
            )
        try:
            for message in invocation.input_messages:
                permissions.assert_input(message)
                if message.market_id not in {None, invocation.market_id}:
                    raise PermissionViolation(
                        "input market_id differs from invocation"
                    )
                if message.policy_version != invocation.policy_version:
                    raise PermissionViolation(
                        "input policy_version differs from invocation"
                    )
                age_ms = (
                    invocation.invoked_at - message.received_at
                ).total_seconds() * 1_000
                if age_ms < 0:
                    raise PermissionViolation("input was received in the future")
                if age_ms > contract.max_input_age_ms:
                    return self._abstain(invocation, "stale_input_message")
        except PermissionViolation as exc:
            return self._degrade(invocation, str(exc), invalid_output=True)

        try:
            raw_output = self._handlers[invocation.agent_id](invocation)
        except Exception as exc:
            return self._degrade(
                invocation,
                f"handler_exception:{type(exc).__name__}",
                invalid_output=False,
            )
        if raw_output is None:
            return self._abstain(invocation, "handler_abstained")
        outputs = raw_output if isinstance(raw_output, tuple) else (raw_output,)
        if not outputs or len(outputs) > contract.budget.max_messages_per_invocation:
            return self._degrade(
                invocation,
                "output_message_budget_exceeded",
                invalid_output=True,
            )
        try:
            for message in outputs:
                if not isinstance(message, MessageEnvelope):
                    raise PermissionViolation("handler returned a non-message output")
                permissions.assert_output(
                    message,
                    market_id=invocation.market_id,
                    policy_version=invocation.policy_version,
                )
                payload_size = len(
                    json.dumps(
                        message.to_dict()["payload"],
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                if payload_size > contract.budget.max_payload_bytes:
                    raise PermissionViolation("output payload budget exceeded")
        except (PermissionViolation, TypeError, ValueError) as exc:
            return self._degrade(invocation, str(exc), invalid_output=True)

        self._failures[invocation.agent_id] = 0
        self._last_success[invocation.agent_id] = invocation.invoked_at
        return self._result(
            invocation,
            InvocationStatus.COMPLETED,
            outputs=outputs,
        )

    def health(self, agent_id: str, *, now: datetime) -> AgentHealth:
        lifecycle = self.lifecycle(agent_id)
        if lifecycle.state is AgentState.RETIRED:
            status = HealthStatus.RETIRED
            return AgentHealth(
                agent_id=agent_id,
                status=status,
                evaluated_at=now,
                consecutive_failures=self._failures[agent_id],
                invalid_outputs=self._invalid_outputs[agent_id],
                last_success_at=self._last_success[agent_id],
                last_failure_at=self._last_failure[agent_id],
                reasons=("retired",),
                metrics={},
            )
        evaluated = self.health_policy.evaluate(
            agent_id=agent_id,
            now=now,
            consecutive_failures=self._failures[agent_id],
            invalid_outputs=self._invalid_outputs[agent_id],
            last_success_at=self._last_success[agent_id],
            last_failure_at=self._last_failure[agent_id],
            warming=lifecycle.state in {AgentState.REGISTERED, AgentState.WARMING},
        )
        lifecycle_status = {
            AgentState.REGISTERED: HealthStatus.WARMING,
            AgentState.WARMING: HealthStatus.WARMING,
            AgentState.READY: HealthStatus.WARMING,
            AgentState.DEGRADED: HealthStatus.DEGRADED,
            AgentState.ABSTAINING: HealthStatus.ABSTAINING,
            AgentState.QUARANTINED: HealthStatus.QUARANTINED,
        }.get(lifecycle.state)
        if lifecycle_status is None or evaluated.status is HealthStatus.QUARANTINED:
            return evaluated
        if evaluated.status is lifecycle_status:
            return evaluated
        return AgentHealth(
            agent_id=evaluated.agent_id,
            status=lifecycle_status,
            evaluated_at=evaluated.evaluated_at,
            consecutive_failures=evaluated.consecutive_failures,
            invalid_outputs=evaluated.invalid_outputs,
            last_success_at=evaluated.last_success_at,
            last_failure_at=evaluated.last_failure_at,
            reasons=(*evaluated.reasons, f"lifecycle_{lifecycle.state.value.lower()}"),
            metrics=evaluated.metrics,
        )
