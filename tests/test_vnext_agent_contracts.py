from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dummy.agents import (
    AgentBudget,
    AgentContract,
    AgentLifecycle,
    AgentRegistry,
    AgentRole,
    AgentState,
    AgentVertical,
    ContractValidationError,
    HealthPolicy,
    HealthStatus,
    LifecycleTransitionError,
    RegistryError,
)
from dummy.chronos import ClockDomain
from dummy.constitution import Authority
from dummy.protocols import MessageType


NOW = datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)


def _contract(agent_id: str = "market-prior-v1", **overrides: object) -> AgentContract:
    values: dict[str, object] = {
        "agent_id": agent_id,
        "role": AgentRole.MARKET_PRIOR,
        "vertical": AgentVertical.MARKET,
        "supported_market_types": ("winner", "15m_direction"),
        "input_types": (MessageType.OBSERVATION,),
        "output_types": (MessageType.FORECAST,),
        "clock_domain": ClockDomain.PREGAME,
        "authority": Authority.FORECAST,
        "evidence_requirements": ("fresh_market_view",),
        "fail_closed_on": ("missing_book", "stale_market"),
        "budget": AgentBudget(),
        "calibration_identity": "market-price-v1",
        "source_family": "market-prior",
        "version": "1.0.0",
    }
    values.update(overrides)
    return AgentContract(**values)  # type: ignore[arg-type]


def test_contract_is_canonical_and_deterministic() -> None:
    contract = _contract(
        supported_market_types=("winner", "15m_direction"),
        fail_closed_on=("stale_market", "missing_book"),
    )
    assert contract.supported_market_types == ("15m_direction", "winner")
    assert contract.fail_closed_on == ("missing_book", "stale_market")
    assert contract.digest() == contract.digest()
    assert len(contract.digest()) == 64
    assert contract.to_dict()["maturity"] == "EXPERIMENTAL_SOVEREIGN_FORECASTING"
    assert contract.to_dict()["output_schemas"] == [
        {
            "message_type": "FORECAST",
            "schema_id": "dummy.protocols.forecast",
            "schema_version": 1,
        }
    ]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"agent_id": "INVALID ID"}, "invalid agent_id"),
        ({"authority": Authority.RECOMMEND}, "research authority ceiling"),
        (
            {
                "authority": Authority.MODEL,
                "output_types": (MessageType.FORECAST,),
            },
            "requires FORECAST",
        ),
        ({"fail_closed_on": ()}, "fail_closed_on must be non-empty"),
        ({"dependencies": ("market-prior-v1",)}, "depend on itself"),
        ({"max_input_age_ms": 0}, "max_input_age_ms must be positive"),
    ],
)
def test_contract_rejects_unsafe_or_incomplete_declarations(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ContractValidationError, match=message):
        _contract(**overrides)


def test_lifecycle_requires_every_activation_state() -> None:
    lifecycle = AgentLifecycle("market-prior-v1")
    with pytest.raises(LifecycleTransitionError, match="invalid transition"):
        lifecycle.transition(AgentState.ACTIVE, at=NOW, reason="skip")

    warming = lifecycle.transition(AgentState.WARMING, at=NOW, reason="warm")
    ready = lifecycle.transition(AgentState.READY, at=NOW, reason="ready")
    active = lifecycle.transition(AgentState.ACTIVE, at=NOW, reason="active")
    assert lifecycle.state is AgentState.ACTIVE
    assert [item.sequence for item in lifecycle.history] == [1, 2, 3]
    assert len({warming.transition_id, ready.transition_id, active.transition_id}) == 3


def test_quarantine_release_requires_review_and_retirement_is_terminal() -> None:
    lifecycle = AgentLifecycle("market-prior-v1")
    lifecycle.transition(
        AgentState.QUARANTINED,
        at=NOW,
        reason="invalid output",
        evidence_ids=("invalid-output-1",),
    )
    with pytest.raises(LifecycleTransitionError, match="review authorization"):
        lifecycle.transition(AgentState.WARMING, at=NOW, reason="retry")
    lifecycle.transition(
        AgentState.WARMING,
        at=NOW,
        reason="reviewed retry",
        evidence_ids=("review-1",),
        review_authorized=True,
    )
    lifecycle.transition(
        AgentState.RETIRED,
        at=NOW,
        reason="no contribution",
        evidence_ids=("retirement-review-1",),
    )
    with pytest.raises(LifecycleTransitionError, match="invalid transition"):
        lifecycle.transition(AgentState.WARMING, at=NOW, reason="resurrect")


@pytest.mark.parametrize(
    "target",
    [AgentState.DEGRADED, AgentState.QUARANTINED, AgentState.RETIRED],
)
def test_adverse_lifecycle_transitions_require_evidence(target: AgentState) -> None:
    lifecycle = AgentLifecycle("market-prior-v1")
    if target is AgentState.DEGRADED:
        lifecycle.transition(AgentState.WARMING, at=NOW, reason="warm")
    with pytest.raises(LifecycleTransitionError, match="requires evidence_ids"):
        lifecycle.transition(target, at=NOW, reason="no evidence")


def test_lifecycle_time_cannot_move_backward() -> None:
    lifecycle = AgentLifecycle("market-prior-v1")
    lifecycle.transition(AgentState.WARMING, at=NOW, reason="warm")
    with pytest.raises(LifecycleTransitionError, match="time moved backward"):
        lifecycle.transition(
            AgentState.READY,
            at=NOW - timedelta(microseconds=1),
            reason="ready",
        )


def test_registry_seals_in_deterministic_dependency_order() -> None:
    registry = AgentRegistry()
    child = _contract("calibrator-v1", dependencies=("market-prior-v1",))
    registry.register(child)
    registry.register(_contract())
    assert registry.seal() == ("market-prior-v1", "calibrator-v1")
    assert registry.seal() == ("market-prior-v1", "calibrator-v1")
    assert registry.by_source_family() == {
        "market-prior": ("calibrator-v1", "market-prior-v1")
    }
    with pytest.raises(RegistryError, match="sealed registry"):
        registry.register(_contract("another-v1"))


def test_registry_rejects_missing_and_cyclic_dependencies() -> None:
    missing = AgentRegistry()
    missing.register(_contract(dependencies=("absent-v1",)))
    with pytest.raises(RegistryError, match="missing dependencies"):
        missing.seal()

    cyclic = AgentRegistry()
    cyclic.register(_contract("first-v1", dependencies=("second-v1",)))
    cyclic.register(_contract("second-v1", dependencies=("first-v1",)))
    with pytest.raises(RegistryError, match="cyclic agent dependencies"):
        cyclic.seal()


def test_health_policy_degrades_quarantines_and_detects_staleness() -> None:
    policy = HealthPolicy(
        degrade_after_failures=1,
        quarantine_after_failures=3,
        quarantine_after_invalid_outputs=2,
        stale_after=timedelta(minutes=5),
    )
    stale = policy.evaluate(
        agent_id="market-prior-v1",
        now=NOW,
        consecutive_failures=0,
        invalid_outputs=0,
        last_success_at=NOW - timedelta(minutes=6),
        last_failure_at=None,
    )
    assert stale.status is HealthStatus.ABSTAINING
    assert stale.reasons == ("stale_success_lease",)

    degraded = policy.evaluate(
        agent_id="market-prior-v1",
        now=NOW,
        consecutive_failures=1,
        invalid_outputs=0,
        last_success_at=NOW,
        last_failure_at=NOW,
    )
    assert degraded.status is HealthStatus.DEGRADED

    quarantined = policy.evaluate(
        agent_id="market-prior-v1",
        now=NOW,
        consecutive_failures=0,
        invalid_outputs=2,
        last_success_at=NOW,
        last_failure_at=NOW,
    )
    assert quarantined.status is HealthStatus.QUARANTINED
