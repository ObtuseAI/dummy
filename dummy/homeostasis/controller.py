"""Pure Phase 7 health evaluation and intervention proposal controller."""

from __future__ import annotations

from dummy.constitution import Authority
from dummy.homeostasis.health_state import HealthLevel, HomeostasisState, VariableHealth
from dummy.homeostasis.interventions import Intervention, InterventionProposal
from dummy.homeostasis.variables import (
    HealthPolicy,
    HealthReading,
    HealthVariable,
    RiskDirection,
)
from dummy.world_model.models import digest_json


def _policy(
    variable: HealthVariable,
    direction: RiskDirection,
    thresholds: tuple[float, float, float],
    *interventions: Intervention,
    target: float | None = None,
) -> HealthPolicy:
    return HealthPolicy(
        variable=variable,
        direction=direction,
        healthy_boundary=thresholds[0],
        warning_boundary=thresholds[1],
        critical_boundary=thresholds[2],
        target=target,
        interventions=tuple(item.value for item in interventions),
    )


DEFAULT_HEALTH_POLICIES = (
    _policy(HealthVariable.CALIBRATION_ERROR, RiskDirection.HIGHER_IS_WORSE, (0.08, 0.14, 0.22), Intervention.ABSTAIN, Intervention.REQUEST_HUMAN_REVIEW),
    _policy(HealthVariable.SOURCE_CONCENTRATION, RiskDirection.HIGHER_IS_WORSE, (0.55, 0.70, 0.82), Intervention.CAP_FAMILY_WEIGHT, Intervention.SPAWN_INDEPENDENT_CHALLENGER),
    _policy(HealthVariable.MODEL_FAMILY_CONCENTRATION, RiskDirection.HIGHER_IS_WORSE, (0.55, 0.70, 0.82), Intervention.CAP_FAMILY_WEIGHT, Intervention.INCREASE_MARKET_ANCHOR, Intervention.RUN_FAMILY_ABLATION),
    _policy(HealthVariable.CONTESTED_PERFORMANCE, RiskDirection.LOWER_IS_WORSE, (0.52, 0.48, 0.42), Intervention.ABSTAIN, Intervention.REQUEST_HUMAN_REVIEW),
    _policy(HealthVariable.FORECAST_DIVERSITY, RiskDirection.LOWER_IS_WORSE, (0.45, 0.30, 0.15), Intervention.SPAWN_INDEPENDENT_CHALLENGER, Intervention.RUN_FAMILY_ABLATION),
    _policy(HealthVariable.MARKET_COVERAGE, RiskDirection.LOWER_IS_WORSE, (0.70, 0.50, 0.30), Intervention.REQUEST_EVIDENCE),
    _policy(HealthVariable.DATA_FRESHNESS, RiskDirection.LOWER_IS_WORSE, (0.85, 0.65, 0.40), Intervention.ABSTAIN, Intervention.REQUEST_SOURCE_REFRESH),
    _policy(HealthVariable.LEDGER_HEALTH, RiskDirection.LOWER_IS_WORSE, (0.98, 0.90, 0.75), Intervention.PAUSE_MUTATION, Intervention.QUARANTINE_COMPONENT),
    _policy(HealthVariable.FILL_REALISM, RiskDirection.LOWER_IS_WORSE, (0.80, 0.60, 0.35), Intervention.ABSTAIN, Intervention.REQUEST_HUMAN_REVIEW),
    _policy(HealthVariable.SETTLEMENT_LAG, RiskDirection.HIGHER_IS_WORSE, (0.20, 0.45, 0.70), Intervention.PAUSE_MUTATION, Intervention.REQUEST_EVIDENCE),
    _policy(HealthVariable.SIMULATION_DETERMINISM, RiskDirection.LOWER_IS_WORSE, (1.00, 0.98, 0.90), Intervention.PAUSE_MUTATION, Intervention.QUARANTINE_COMPONENT),
    _policy(HealthVariable.QUEUE_PRESSURE, RiskDirection.HIGHER_IS_WORSE, (0.55, 0.75, 0.90), Intervention.REDUCE_QUEUE_INTAKE),
    _policy(HealthVariable.COMPUTE_PRESSURE, RiskDirection.HIGHER_IS_WORSE, (0.60, 0.78, 0.92), Intervention.REDUCE_COMPUTE_BUDGET),
    _policy(HealthVariable.MUTATION_PRESSURE, RiskDirection.HIGHER_IS_WORSE, (0.35, 0.55, 0.75), Intervention.PAUSE_MUTATION),
    _policy(HealthVariable.CHALLENGER_SURVIVAL, RiskDirection.LOWER_IS_WORSE, (0.35, 0.20, 0.08), Intervention.PAUSE_MUTATION, Intervention.RUN_FAMILY_ABLATION),
    _policy(HealthVariable.OVERCONFIDENCE_RATE, RiskDirection.HIGHER_IS_WORSE, (0.08, 0.15, 0.25), Intervention.ABSTAIN, Intervention.INCREASE_MARKET_ANCHOR),
    _policy(HealthVariable.ABSTENTION_RATE, RiskDirection.DISTANCE_FROM_TARGET, (0.18, 0.32, 0.50), Intervention.REQUEST_HUMAN_REVIEW, target=0.35),
    _policy(HealthVariable.LIVE_GATE_DISTANCE, RiskDirection.HIGHER_IS_WORSE, (0.25, 0.50, 0.75), Intervention.ABSTAIN, Intervention.REQUEST_HUMAN_REVIEW),
    _policy(HealthVariable.DRIFT_ALERTS, RiskDirection.HIGHER_IS_WORSE, (0.10, 0.25, 0.45), Intervention.ABSTAIN, Intervention.QUARANTINE_COMPONENT, Intervention.REQUEST_SOURCE_REFRESH),
)


def _level(reading: HealthReading, policy: HealthPolicy) -> tuple[HealthLevel, str]:
    if reading.value is None:
        return HealthLevel.UNKNOWN, "measurement_unavailable_fail_closed"
    value = reading.value
    if policy.direction is RiskDirection.DISTANCE_FROM_TARGET:
        risk = abs(value - float(policy.target))
        label = "distance_from_target"
    elif policy.direction is RiskDirection.HIGHER_IS_WORSE:
        risk = value
        label = "higher_is_worse"
    else:
        risk = value
        label = "lower_is_worse"

    if policy.direction is RiskDirection.LOWER_IS_WORSE:
        if risk >= policy.healthy_boundary:
            level = HealthLevel.HEALTHY
        elif risk >= policy.warning_boundary:
            level = HealthLevel.ELEVATED
        elif risk >= policy.critical_boundary:
            level = HealthLevel.WARNING
        else:
            level = HealthLevel.CRITICAL
    else:
        if risk <= policy.healthy_boundary:
            level = HealthLevel.HEALTHY
        elif risk <= policy.warning_boundary:
            level = HealthLevel.ELEVATED
        elif risk <= policy.critical_boundary:
            level = HealthLevel.WARNING
        else:
            level = HealthLevel.CRITICAL
    return level, f"{label}:{risk:.6f}:{level.name.lower()}"


def evaluate_homeostasis(
    readings: tuple[HealthReading, ...],
    *,
    policies: tuple[HealthPolicy, ...] = DEFAULT_HEALTH_POLICIES,
) -> HomeostasisState:
    policy_map = {item.variable: item for item in policies}
    reading_map = {item.variable: item for item in readings}
    if len(policy_map) != len(policies) or len(reading_map) != len(readings):
        raise ValueError("homeostasis inputs contain duplicate variables")
    if set(reading_map) != set(policy_map):
        raise ValueError("homeostasis requires exactly one reading per policy")
    results = tuple(
        VariableHealth(
            variable=variable,
            level=_level(reading_map[variable], policy_map[variable])[0],
            reading=reading_map[variable],
            policy=policy_map[variable],
            reason=_level(reading_map[variable], policy_map[variable])[1],
        )
        for variable in sorted(policy_map, key=lambda item: item.value)
    )
    evidence_ids = tuple(sorted({item for reading in readings for item in reading.evidence_ids}))
    semantic = {
        "schema_version": 1,
        "variables": [item.to_dict() for item in results],
        "overall_level": max(item.level for item in results).name,
        "evidence_ids": list(evidence_ids),
        "authority_expansion_allowed": False,
    }
    return HomeostasisState(
        state_id=digest_json(semantic),
        variables=results,
        overall_level=max(item.level for item in results),
        evidence_ids=evidence_ids,
    )


def propose_interventions(state: HomeostasisState) -> tuple[InterventionProposal, ...]:
    proposals: list[InterventionProposal] = []
    for result in state.variables:
        if result.level is HealthLevel.HEALTHY:
            continue
        interventions = (
            (Intervention.REQUEST_EVIDENCE,)
            if result.level is HealthLevel.UNKNOWN
            else tuple(Intervention(item) for item in result.policy.interventions)
        )
        semantic = {
            "schema_version": 1,
            "state_id": state.state_id,
            "variable": result.variable.value,
            "level": result.level.name,
            "interventions": sorted(item.value for item in interventions),
            "evidence_ids": list(result.reading.evidence_ids),
            "authority_before": Authority.SIMULATE.name,
            "authority_after": Authority.SIMULATE.name,
            "automatic_eligible": all(
                item.value
                in {
                    "abstain",
                    "cap_family_weight",
                    "increase_market_anchor",
                    "pause_mutation",
                    "quarantine_component",
                    "reduce_compute_budget",
                    "reduce_queue_intake",
                    "request_evidence",
                    "request_source_refresh",
                }
                for item in interventions
            ),
            "applied": False,
            "authority_expansion": False,
        }
        proposals.append(
            InterventionProposal(
                proposal_id=digest_json(semantic),
                state_id=state.state_id,
                variable=result.variable,
                level=result.level,
                interventions=interventions,
                evidence_ids=result.reading.evidence_ids,
                authority_before=Authority.SIMULATE,
                authority_after=Authority.SIMULATE,
                automatic_eligible=bool(semantic["automatic_eligible"]),
            )
        )
    return tuple(sorted(proposals, key=lambda item: item.proposal_id))


__all__ = [
    "DEFAULT_HEALTH_POLICIES",
    "evaluate_homeostasis",
    "propose_interventions",
]
