from __future__ import annotations

from datetime import datetime, timezone

import pytest

from dummy.constitution import Authority
from dummy.homeostasis import (
    DEFAULT_HEALTH_POLICIES,
    HealthLevel,
    HealthReading,
    HealthVariable,
    Intervention,
    InterventionProposal,
    RiskDirection,
    evaluate_homeostasis,
    propose_interventions,
)


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


def _healthy_value(policy) -> float:
    if policy.direction is RiskDirection.HIGHER_IS_WORSE:
        return policy.healthy_boundary
    if policy.direction is RiskDirection.LOWER_IS_WORSE:
        return policy.healthy_boundary
    return float(policy.target)


def _readings(*, override: dict[HealthVariable, float | None] | None = None):
    override = override or {}
    return tuple(
        HealthReading(
            variable=policy.variable,
            value=override.get(policy.variable, _healthy_value(policy)),
            observed_at=NOW,
            evidence_ids=(
                ()
                if policy.variable in override and override[policy.variable] is None
                else (f"evidence:{policy.variable.value}",)
            ),
            source_reference=f"fixture:{policy.variable.value}",
        )
        for policy in DEFAULT_HEALTH_POLICIES
    )


def test_canonical_homeostasis_covers_every_planned_variable() -> None:
    assert len(HealthVariable) == 19
    assert len(DEFAULT_HEALTH_POLICIES) == len(HealthVariable)
    assert {item.variable for item in DEFAULT_HEALTH_POLICIES} == set(HealthVariable)


def test_healthy_state_is_deterministic_and_needs_no_intervention() -> None:
    first = evaluate_homeostasis(_readings())
    second = evaluate_homeostasis(_readings())
    assert first.to_dict() == second.to_dict()
    assert first.overall_level is HealthLevel.HEALTHY
    assert propose_interventions(first) == ()
    assert first.authority_expansion_allowed is False


def test_unknown_reading_fails_closed_and_requests_evidence() -> None:
    state = evaluate_homeostasis(
        _readings(override={HealthVariable.DATA_FRESHNESS: None})
    )
    result = next(
        item for item in state.variables if item.variable is HealthVariable.DATA_FRESHNESS
    )
    assert result.level is HealthLevel.UNKNOWN
    proposal = next(
        item
        for item in propose_interventions(state)
        if item.variable is HealthVariable.DATA_FRESHNESS
    )
    assert proposal.interventions == (Intervention.REQUEST_EVIDENCE,)
    assert proposal.automatic_eligible is True
    assert proposal.authority_after <= proposal.authority_before
    assert proposal.applied is False


def test_concentration_intervention_is_not_silently_applied() -> None:
    state = evaluate_homeostasis(
        _readings(override={HealthVariable.MODEL_FAMILY_CONCENTRATION: 0.95})
    )
    proposal = next(
        item
        for item in propose_interventions(state)
        if item.variable is HealthVariable.MODEL_FAMILY_CONCENTRATION
    )
    assert proposal.level is HealthLevel.CRITICAL
    assert Intervention.CAP_FAMILY_WEIGHT in proposal.interventions
    assert Intervention.SPAWN_INDEPENDENT_CHALLENGER not in proposal.interventions
    assert proposal.automatic_eligible is False
    assert proposal.applied is False


def test_homeostasis_contract_rejects_authority_expansion() -> None:
    with pytest.raises(ValueError, match="cannot expand authority"):
        InterventionProposal(
            proposal_id="invalid",
            state_id="state",
            variable=HealthVariable.DATA_FRESHNESS,
            level=HealthLevel.WARNING,
            interventions=(Intervention.REQUEST_EVIDENCE,),
            evidence_ids=("evidence",),
            authority_before=Authority.OBSERVE,
            authority_after=Authority.SIMULATE,
            automatic_eligible=True,
        )
