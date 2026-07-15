from __future__ import annotations

from dummy.arenas import (
    ArenaCategory,
    ArenaDomain,
    ArenaInput,
    ArenaResponse,
    ArenaScenario,
    StressSignal,
    arena_catalog,
    arena_reproducibility_report,
    replay_arena,
    run_arena,
)
from dummy.constitution import Authority, evaluate_mutation_proposal
from dummy.world_model.models import digest_json


def _inputs(*, authority: Authority = Authority.SIMULATE) -> ArenaInput:
    return ArenaInput(
        forecast_probability=0.61,
        market_prior=0.56,
        uncertainty=0.16,
        evidence_ids=("arena-input-evidence",),
        authority=authority,
    )


def test_catalog_contains_every_master_plan_arena() -> None:
    scenarios = arena_catalog()
    assert len(scenarios) == 40
    assert len({item.scenario_id for item in scenarios}) == 40
    assert {domain: sum(item.domain is domain for item in scenarios) for domain in ArenaDomain} == {
        ArenaDomain.FORECAST: 11,
        ArenaDomain.SPORTS: 10,
        ArenaDomain.CRYPTO: 10,
        ArenaDomain.METACOGNITIVE: 9,
    }
    assert {item.category for item in scenarios} == set(ArenaCategory)
    assert all(item.empirical is False for item in scenarios)


def test_every_catalog_arena_replays_identically_and_passes() -> None:
    for scenario in arena_catalog():
        replay = replay_arena(scenario, _inputs())
        assert replay["deterministic"] is True
        assert replay["passed"] is True
        assert replay["authority_expanded"] is False
        assert replay["empirical_claim_supported"] is False


def test_arena_preserves_even_lower_input_authority() -> None:
    result = run_arena(arena_catalog()[0], _inputs(authority=Authority.OBSERVE))
    assert result.authority_before is Authority.OBSERVE
    assert result.authority_after is Authority.OBSERVE


def test_arena_can_fail_an_unmet_response_contract() -> None:
    semantic = {
        "schema_version": 1,
        "name": "impossible concentration response",
        "domain": ArenaDomain.FORECAST.value,
        "category": ArenaCategory.LEAKAGE.value,
        "signal": StressSignal.CONCENTRATION.value,
        "severity": 0.9,
        "expected_responses": [ArenaResponse.VETO.value],
        "evidence_ids": ["test-scenario"],
        "empirical": False,
    }
    scenario = ArenaScenario(
        scenario_id=digest_json(semantic),
        name="impossible concentration response",
        domain=ArenaDomain.FORECAST,
        category=ArenaCategory.LEAKAGE,
        signal=StressSignal.CONCENTRATION,
        severity=0.9,
        expected_responses=(ArenaResponse.VETO,),
        evidence_ids=("test-scenario",),
    )
    assert run_arena(scenario, _inputs()).passed is False


def test_arena_report_is_mechanical_not_empirical() -> None:
    report = arena_reproducibility_report()
    assert report["scenario_count"] == 40
    assert report["passing_count"] == 40
    assert report["deterministic_count"] == 40
    assert report["runtime_episode_count"] == 0
    assert report["empirical_claim_supported"] is False


def test_evolution_cannot_mutate_the_arena_judge() -> None:
    decision = evaluate_mutation_proposal(
        ["dummy/arenas/runner.py"],
        proposer_authority=Authority.RECOMMEND,
    )
    assert decision.allowed is False
    assert decision.blocked_paths == ("dummy/arenas/runner.py",)
