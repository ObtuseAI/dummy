from __future__ import annotations

import pytest

from dummy.synthesis import (
    FamilyCapPolicy,
    SynthesisSource,
    SynthesisValidationError,
    synthesize,
)


def _source(
    agent_id: str,
    role: str,
    family: str,
    probability: float,
    weight: float,
    *,
    calibrated: bool = True,
    stale: bool = False,
) -> SynthesisSource:
    return SynthesisSource(
        agent_id=agent_id,
        role=role,
        family_id=family,
        probability_yes=probability,
        uncertainty=0.08,
        proposed_weight=weight,
        calibrated=calibrated,
        stale=stale,
        regime_relevance=1.0,
        independence=1.0,
        evidence_ids=(f"evidence-{agent_id}",),
    )


def test_market_floor_and_family_caps_hold_under_alias_duplication() -> None:
    result = synthesize(
        (
            _source("prior", "market_prior", "market-price", 0.50, 0.50),
            _source("alias-a", "specialist", "same-family", 0.90, 0.35),
            _source("alias-b", "specialist", "same-family", 0.90, 0.35),
            _source(
                "counter",
                "contrarian",
                "counter-family",
                0.20,
                0.15,
                calibrated=False,
            ),
        ),
        policy=FamilyCapPolicy(),
    )
    families = dict(result.family_weights)
    assert result.market_prior_weight >= 0.50
    assert families["same-family"] <= 0.35
    assert families["counter-family"] <= 0.15
    assert sum(families.values()) == pytest.approx(1.0)
    assert result.probability_yes < 0.90


def test_stale_source_gets_exactly_zero_influence() -> None:
    result = synthesize(
        (
            _source("prior", "market_prior", "market-price", 0.50, 0.50),
            _source("stale", "specialist", "stale-family", 0.99, 0.35, stale=True),
        ),
        policy=FamilyCapPolicy(),
    )
    assert result.probability_yes == 0.50
    assert dict(result.source_weights) == {"prior": 1.0}
    assert result.excluded_sources == (("stale", "stale_source_zero_weight"),)


def test_shadow_cap_can_reduce_but_never_increase_family_influence() -> None:
    sources = (
        _source("prior", "market_prior", "market-price", 0.50, 0.50),
        _source("specialist", "specialist", "specialist-family", 0.80, 0.35),
        _source(
            "counter",
            "contrarian",
            "counter-family",
            0.20,
            0.15,
            calibrated=False,
        ),
    )
    baseline = synthesize(sources, policy=FamilyCapPolicy())
    guarded = synthesize(
        sources,
        policy=FamilyCapPolicy(),
        family_influence_caps={"specialist-family": 0.5},
    )
    assert dict(guarded.family_weights)["specialist-family"] < dict(
        baseline.family_weights
    )["specialist-family"]
    assert guarded.market_prior_weight >= baseline.market_prior_weight
    with pytest.raises(SynthesisValidationError, match=r"in \[0, 1\]"):
        synthesize(
            sources,
            policy=FamilyCapPolicy(),
            family_influence_caps={"specialist-family": 1.01},
        )


def test_missing_or_stale_market_prior_fails_closed() -> None:
    with pytest.raises(SynthesisValidationError, match="market-price prior"):
        synthesize(
            (_source("specialist", "specialist", "family", 0.6, 1.0),),
            policy=FamilyCapPolicy(),
        )
    with pytest.raises(SynthesisValidationError, match="market-price prior"):
        synthesize(
            (
                _source(
                    "prior",
                    "market_prior",
                    "market-price",
                    0.5,
                    1.0,
                    stale=True,
                ),
            ),
            policy=FamilyCapPolicy(),
        )


def test_reviewed_market_prior_floor_cannot_be_weakened() -> None:
    with pytest.raises(SynthesisValidationError, match="incoherent"):
        FamilyCapPolicy(market_prior_floor=0.49)


def test_synthesis_is_deterministic_and_interval_contains_probability() -> None:
    sources = (
        _source("prior", "market_prior", "market-price", 0.48, 0.50),
        _source("specialist", "specialist", "family", 0.62, 0.35),
    )
    first = synthesize(sources, policy=FamilyCapPolicy())
    second = synthesize(sources, policy=FamilyCapPolicy())
    assert first == second
    assert first.uncertainty_interval[0] <= first.probability_yes
    assert first.probability_yes <= first.uncertainty_interval[1]
