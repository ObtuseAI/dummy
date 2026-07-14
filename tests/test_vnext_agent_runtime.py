from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dummy.agents import (
    AgentBudget,
    AgentContract,
    AgentInvocation,
    AgentRole,
    AgentRuntime,
    AgentState,
    AgentVertical,
    DeterministicMailbox,
    HealthPolicy,
    HealthStatus,
    InvocationStatus,
    MailboxError,
    RegistryError,
)
from dummy.chronos import ClockDomain
from dummy.constitution import Authority
from dummy.protocols import MessageEnvelope, MessageType


NOW = datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)
MARKET = "KXBTC15M-26JUL142215-15"


def _contract(
    agent_id: str,
    *,
    inputs: tuple[MessageType, ...],
    outputs: tuple[MessageType, ...],
    authority: Authority,
    dependencies: tuple[str, ...] = (),
) -> AgentContract:
    return AgentContract(
        agent_id=agent_id,
        role=AgentRole.MARKET_PRIOR,
        vertical=AgentVertical.CRYPTO,
        supported_market_types=("15m_direction",),
        input_types=inputs,
        output_types=outputs,
        clock_domain=ClockDomain.FIFTEEN_MINUTE,
        authority=authority,
        evidence_requirements=("fresh_market_view",),
        fail_closed_on=("missing_market", "stale_market"),
        budget=AgentBudget(max_messages_per_invocation=2),
        calibration_identity=f"{agent_id}-cal",
        source_family=f"{agent_id}-family",
        version="1.0.0",
        dependencies=dependencies,
    )


def _observation(
    sender: str = "scanner-v1",
    *,
    policy_version: str = "policy-1",
    received_at: datetime = NOW,
) -> MessageEnvelope:
    return MessageEnvelope.create(
        message_type=MessageType.OBSERVATION,
        sender=sender,
        market_id=MARKET,
        issued_at=NOW,
        effective_time=NOW,
        received_at=received_at,
        model_version="scanner-1",
        policy_version=policy_version,
        payload={"yes_bid": 49, "yes_ask": 51},
    )


def _forecast(sender: str = "prior-v1", probability: float = 0.5) -> MessageEnvelope:
    return MessageEnvelope.create(
        message_type=MessageType.FORECAST,
        sender=sender,
        market_id=MARKET,
        issued_at=NOW,
        effective_time=NOW,
        received_at=NOW,
        model_version="prior-1",
        policy_version="policy-1",
        payload={"probability": probability},
        evidence_ids=(_observation().message_id,),
    )


def _invocation(**overrides: object) -> AgentInvocation:
    values: dict[str, object] = {
        "agent_id": "prior-v1",
        "market_id": MARKET,
        "market_type": "15m_direction",
        "clock_domain": ClockDomain.FIFTEEN_MINUTE,
        "policy_version": "policy-1",
        "invoked_at": NOW,
        "evidence_keys": ("fresh_market_view",),
        "input_messages": (_observation(),),
    }
    values.update(overrides)
    return AgentInvocation.create(**values)  # type: ignore[arg-type]


def test_invocation_identity_is_deterministic() -> None:
    first = _invocation()
    second = _invocation()
    assert first.invocation_id == second.invocation_id


def test_mailbox_orders_recipients_and_rejects_duplicate_delivery() -> None:
    from dummy.agents import AgentRegistry

    registry = AgentRegistry()
    registry.register(
        _contract(
            "scanner-v1",
            inputs=(),
            outputs=(MessageType.OBSERVATION,),
            authority=Authority.OBSERVE,
        )
    )
    for agent_id in ("prior-v1", "specialist-v1"):
        registry.register(
            _contract(
                agent_id,
                inputs=(MessageType.OBSERVATION,),
                outputs=(MessageType.FORECAST,),
                authority=Authority.FORECAST,
            )
        )
    registry.seal()
    mailbox = DeterministicMailbox(
        registry,
        state_lookup=lambda _agent_id: AgentState.ACTIVE,
    )
    message = _observation()
    delivered = mailbox.publish(
        sender="scanner-v1",
        recipients=("specialist-v1", "prior-v1"),
        message=message,
    )
    assert [item.recipient for item in delivered] == ["prior-v1", "specialist-v1"]
    assert [item.sequence for item in delivered] == [1, 2]
    assert mailbox.read("specialist-v1") == (delivered[1],)
    with pytest.raises(MailboxError, match="duplicate delivery"):
        mailbox.publish(
            sender="scanner-v1",
            recipients=("prior-v1",),
            message=message,
        )


def test_mailbox_rejects_inactive_sender_or_recipient() -> None:
    from dummy.agents import AgentRegistry

    registry = AgentRegistry()
    registry.register(
        _contract(
            "scanner-v1",
            inputs=(),
            outputs=(MessageType.OBSERVATION,),
            authority=Authority.OBSERVE,
        )
    )
    registry.register(
        _contract(
            "prior-v1",
            inputs=(MessageType.OBSERVATION,),
            outputs=(MessageType.FORECAST,),
            authority=Authority.FORECAST,
        )
    )
    registry.seal()
    states = {
        "scanner-v1": AgentState.REGISTERED,
        "prior-v1": AgentState.ACTIVE,
    }
    mailbox = DeterministicMailbox(
        registry,
        state_lookup=states.__getitem__,
    )
    with pytest.raises(MailboxError, match="sender is not active"):
        mailbox.publish(
            sender="scanner-v1",
            recipients=("prior-v1",),
            message=_observation(),
        )
    states["scanner-v1"] = AgentState.ACTIVE
    states["prior-v1"] = AgentState.QUARANTINED
    with pytest.raises(MailboxError, match="recipient is not active"):
        mailbox.publish(
            sender="scanner-v1",
            recipients=("prior-v1",),
            message=_observation(),
        )


def test_runtime_completes_valid_typed_invocation() -> None:
    runtime = AgentRuntime()
    runtime.register(
        _contract(
            "prior-v1",
            inputs=(MessageType.OBSERVATION,),
            outputs=(MessageType.FORECAST,),
            authority=Authority.FORECAST,
        ),
        lambda _request: _forecast(),
    )
    runtime.seal()
    runtime.activate("prior-v1", at=NOW)
    result = runtime.invoke(_invocation())
    assert result.status is InvocationStatus.COMPLETED
    assert result.outputs == (_forecast(),)
    assert result.lifecycle_state is AgentState.ACTIVE


def test_runtime_missing_evidence_abstains_and_requires_recovery() -> None:
    runtime = AgentRuntime()
    runtime.register(
        _contract(
            "prior-v1",
            inputs=(MessageType.OBSERVATION,),
            outputs=(MessageType.FORECAST,),
            authority=Authority.FORECAST,
        ),
        lambda _request: _forecast(),
    )
    runtime.seal()
    runtime.activate("prior-v1", at=NOW)
    result = runtime.invoke(_invocation(evidence_keys=()))
    assert result.status is InvocationStatus.ABSTAINED
    assert result.reasons == ("missing_evidence:fresh_market_view",)
    assert runtime.lifecycle("prior-v1").state is AgentState.ABSTAINING
    assert runtime.health("prior-v1", now=NOW).status is HealthStatus.ABSTAINING

    denied = runtime.invoke(_invocation(invoked_at=NOW + timedelta(seconds=1)))
    assert denied.status is InvocationStatus.DENIED
    runtime.recover("prior-v1", at=NOW + timedelta(seconds=2))
    assert runtime.invoke(
        _invocation(invoked_at=NOW + timedelta(seconds=3))
    ).status is InvocationStatus.COMPLETED


def test_runtime_degrades_wrong_sender_and_quarantines_repeated_invalid_output() -> None:
    runtime = AgentRuntime(
        health_policy=HealthPolicy(quarantine_after_invalid_outputs=2)
    )
    runtime.register(
        _contract(
            "prior-v1",
            inputs=(MessageType.OBSERVATION,),
            outputs=(MessageType.FORECAST,),
            authority=Authority.FORECAST,
        ),
        lambda _request: _forecast(sender="other-v1"),
    )
    runtime.seal()
    runtime.activate("prior-v1", at=NOW)
    first = runtime.invoke(_invocation())
    assert first.status is InvocationStatus.DEGRADED
    runtime.recover("prior-v1", at=NOW + timedelta(seconds=1))
    second = runtime.invoke(_invocation(invoked_at=NOW + timedelta(seconds=2)))
    assert second.status is InvocationStatus.QUARANTINED
    assert runtime.lifecycle("prior-v1").state is AgentState.QUARANTINED
    with pytest.raises(Exception, match="review authorization"):
        runtime.recover("prior-v1", at=NOW + timedelta(seconds=3))
    runtime.recover(
        "prior-v1",
        at=NOW + timedelta(seconds=4),
        review_authorized=True,
        review_evidence_ids=("operator-review-1",),
    )
    assert runtime.health(
        "prior-v1",
        now=NOW + timedelta(seconds=4),
    ).status is HealthStatus.HEALTHY


def test_runtime_rejects_wrong_clock_and_undeclared_input() -> None:
    runtime = AgentRuntime()
    runtime.register(
        _contract(
            "prior-v1",
            inputs=(MessageType.OBSERVATION,),
            outputs=(MessageType.FORECAST,),
            authority=Authority.FORECAST,
        ),
        lambda _request: _forecast(),
    )
    runtime.seal()
    runtime.activate("prior-v1", at=NOW)
    wrong_clock = runtime.invoke(
        _invocation(clock_domain=ClockDomain.HOURLY)
    )
    assert wrong_clock.status is InvocationStatus.ABSTAINED

    runtime.recover("prior-v1", at=NOW + timedelta(seconds=1))
    undeclared = _forecast(sender="upstream-v1")
    result = runtime.invoke(
        _invocation(
            invoked_at=NOW + timedelta(seconds=2),
            input_messages=(undeclared,),
        )
    )
    assert result.status is InvocationStatus.DEGRADED


def test_runtime_rejects_cross_policy_and_stale_inputs() -> None:
    runtime = AgentRuntime()
    runtime.register(
        _contract(
            "prior-v1",
            inputs=(MessageType.OBSERVATION,),
            outputs=(MessageType.FORECAST,),
            authority=Authority.FORECAST,
        ),
        lambda _request: _forecast(),
    )
    runtime.seal()
    runtime.activate("prior-v1", at=NOW)
    cross_policy = runtime.invoke(
        _invocation(input_messages=(_observation(policy_version="other-policy"),))
    )
    assert cross_policy.status is InvocationStatus.DEGRADED
    assert cross_policy.reasons == ("input policy_version differs from invocation",)

    runtime.recover("prior-v1", at=NOW + timedelta(seconds=1))
    stale = runtime.invoke(
        _invocation(
            invoked_at=NOW + timedelta(seconds=61),
            input_messages=(_observation(),),
        )
    )
    assert stale.status is InvocationStatus.ABSTAINED
    assert stale.reasons == ("stale_input_message",)


def test_runtime_requires_active_dependencies_before_activation() -> None:
    runtime = AgentRuntime()
    parent = _contract(
        "prior-v1",
        inputs=(MessageType.OBSERVATION,),
        outputs=(MessageType.FORECAST,),
        authority=Authority.FORECAST,
    )
    child = _contract(
        "calibrator-v1",
        inputs=(MessageType.OBSERVATION,),
        outputs=(MessageType.FORECAST,),
        authority=Authority.FORECAST,
        dependencies=("prior-v1",),
    )
    runtime.register(parent, lambda _request: _forecast())
    runtime.register(child, lambda _request: _forecast(sender="calibrator-v1"))
    runtime.seal()
    with pytest.raises(RegistryError, match="inactive dependencies"):
        runtime.activate("calibrator-v1", at=NOW)
    runtime.activate("prior-v1", at=NOW)
    runtime.activate("calibrator-v1", at=NOW)
    assert runtime.lifecycle("calibrator-v1").state is AgentState.ACTIVE


def test_runtime_sanitizes_handler_exception_and_degrades_agent() -> None:
    def broken(_request):
        raise RuntimeError("sensitive upstream detail")

    runtime = AgentRuntime()
    runtime.register(
        _contract(
            "prior-v1",
            inputs=(MessageType.OBSERVATION,),
            outputs=(MessageType.FORECAST,),
            authority=Authority.FORECAST,
        ),
        broken,
    )
    runtime.seal()
    runtime.activate("prior-v1", at=NOW)
    result = runtime.invoke(_invocation())
    assert result.status is InvocationStatus.DEGRADED
    assert result.reasons == ("handler_exception:RuntimeError",)
    assert "sensitive upstream detail" not in repr(result)


def test_runtime_health_lease_abstains_before_calling_handler() -> None:
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return _forecast()

    runtime = AgentRuntime(
        health_policy=HealthPolicy(stale_after=timedelta(seconds=5))
    )
    runtime.register(
        _contract(
            "prior-v1",
            inputs=(MessageType.OBSERVATION,),
            outputs=(MessageType.FORECAST,),
            authority=Authority.FORECAST,
        ),
        handler,
    )
    runtime.seal()
    runtime.activate("prior-v1", at=NOW)
    assert runtime.invoke(_invocation()).status is InvocationStatus.COMPLETED
    stale = runtime.invoke(
        _invocation(
            invoked_at=NOW + timedelta(seconds=6),
            input_messages=(
                _observation(received_at=NOW + timedelta(seconds=6)),
            ),
        )
    )
    assert stale.status is InvocationStatus.ABSTAINED
    assert stale.reasons == ("health_abstention",)
    assert calls == 1
