"""Pure deterministic response engine for adversarial arena scenarios."""

from __future__ import annotations

from dummy.arenas.models import (
    ArenaInput,
    ArenaResponse,
    ArenaResult,
    ArenaScenario,
    StressSignal,
)
from dummy.world_model.models import digest_json


_RESPONSES: dict[StressSignal, tuple[ArenaResponse, ...]] = {
    StressSignal.CONCENTRATION: (
        ArenaResponse.CAP_INFLUENCE,
        ArenaResponse.INCREASE_MARKET_ANCHOR,
    ),
    StressSignal.DATA_INTEGRITY: (
        ArenaResponse.ABSTAIN,
        ArenaResponse.QUARANTINE,
        ArenaResponse.REQUEST_EVIDENCE,
        ArenaResponse.VETO,
        ArenaResponse.WIDEN_UNCERTAINTY,
    ),
    StressSignal.EXECUTION_REALISM: (
        ArenaResponse.ABSTAIN,
        ArenaResponse.MARK_EXECUTION_IRRELEVANT,
        ArenaResponse.REQUEST_REFRESH,
    ),
    StressSignal.LEAKAGE: (
        ArenaResponse.QUARANTINE,
        ArenaResponse.VETO,
    ),
    StressSignal.LIQUIDITY: (
        ArenaResponse.ABSTAIN,
        ArenaResponse.MARK_EXECUTION_IRRELEVANT,
    ),
    StressSignal.MARKET_PRIOR_CONFLICT: (
        ArenaResponse.INCREASE_MARKET_ANCHOR,
        ArenaResponse.REQUEST_EVIDENCE,
        ArenaResponse.WIDEN_UNCERTAINTY,
    ),
    StressSignal.METACOGNITIVE: (
        ArenaResponse.ABSTAIN,
        ArenaResponse.INCREASE_MARKET_ANCHOR,
        ArenaResponse.QUARANTINE,
        ArenaResponse.REDUCE_RESOURCE_BUDGET,
        ArenaResponse.REQUEST_EVIDENCE,
        ArenaResponse.WIDEN_UNCERTAINTY,
    ),
    StressSignal.REGIME_SHIFT: (
        ArenaResponse.ABSTAIN,
        ArenaResponse.QUARANTINE,
        ArenaResponse.REQUEST_EVIDENCE,
        ArenaResponse.REQUEST_REFRESH,
        ArenaResponse.WIDEN_UNCERTAINTY,
    ),
    StressSignal.STALE_OR_MISSING: (
        ArenaResponse.ABSTAIN,
        ArenaResponse.REQUEST_EVIDENCE,
        ArenaResponse.REQUEST_REFRESH,
    ),
    StressSignal.VOLATILITY_SHOCK: (
        ArenaResponse.ABSTAIN,
        ArenaResponse.QUARANTINE,
        ArenaResponse.REQUEST_REFRESH,
        ArenaResponse.WIDEN_UNCERTAINTY,
    ),
}


def run_arena(scenario: ArenaScenario, inputs: ArenaInput) -> ArenaResult:
    responses = tuple(sorted(_RESPONSES[scenario.signal], key=lambda item: item.value))
    pull = scenario.severity * 0.5
    stressed_probability = round(
        inputs.forecast_probability * (1.0 - pull) + inputs.market_prior * pull,
        12,
    )
    stressed_uncertainty = round(
        min(1.0, inputs.uncertainty + scenario.severity * 0.35),
        12,
    )
    evidence_ids = tuple(sorted(set(inputs.evidence_ids) | set(scenario.evidence_ids)))
    input_digest = digest_json(inputs.to_dict())
    passed = set(scenario.expected_responses).issubset(responses)
    semantic = {
        "schema_version": 1,
        "scenario_id": scenario.scenario_id,
        "input_digest": input_digest,
        "responses": [item.value for item in responses],
        "stressed_probability": stressed_probability,
        "stressed_uncertainty": stressed_uncertainty,
        "evidence_ids": list(evidence_ids),
        "authority_before": inputs.authority.name,
        "authority_after": inputs.authority.name,
        "passed": passed,
        "read_only": True,
        "empirical_claim_supported": False,
    }
    return ArenaResult(
        result_id=digest_json(semantic),
        scenario_id=scenario.scenario_id,
        input_digest=input_digest,
        responses=responses,
        stressed_probability=stressed_probability,
        stressed_uncertainty=stressed_uncertainty,
        evidence_ids=evidence_ids,
        authority_before=inputs.authority,
        authority_after=inputs.authority,
        passed=passed,
    )


def replay_arena(scenario: ArenaScenario, inputs: ArenaInput) -> dict[str, object]:
    first = run_arena(scenario, inputs)
    second = run_arena(scenario, inputs)
    return {
        "scenario_id": scenario.scenario_id,
        "first_result_id": first.result_id,
        "second_result_id": second.result_id,
        "deterministic": first.to_dict() == second.to_dict(),
        "passed": first.passed and second.passed,
        "authority_expanded": False,
        "empirical_claim_supported": False,
    }


__all__ = ["replay_arena", "run_arena"]
