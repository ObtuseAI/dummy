"""Deterministic structured evidence fusion with family and market caps."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Mapping

from .models import (
    CalibrationState,
    FamilyCapPolicy,
    SynthesisResult,
    SynthesisSource,
    SynthesisValidationError,
)


def _allocate_families(
    scores: Mapping[str, float],
    caps: Mapping[str, float],
    budget: float,
) -> dict[str, float]:
    allocations = {family: 0.0 for family in scores}
    active = {family for family, score in scores.items() if score > 0.0}
    remaining = budget
    while active and remaining > 1e-15:
        total_score = sum(scores[family] for family in active)
        if total_score <= 0.0:
            break
        capped = []
        for family in sorted(active):
            desired = remaining * scores[family] / total_score
            available_cap = max(0.0, caps[family] - allocations[family])
            if desired >= available_cap - 1e-15:
                allocations[family] += available_cap
                remaining -= available_cap
                capped.append(family)
        if capped:
            active.difference_update(capped)
            continue
        for family in sorted(active):
            share = remaining * scores[family] / total_score
            allocations[family] += share
        remaining = 0.0
    return allocations


def synthesize(
    sources: tuple[SynthesisSource, ...],
    *,
    policy: FamilyCapPolicy,
    family_influence_caps: Mapping[str, float] | None = None,
    cost_probability: float = 0.0,
) -> SynthesisResult:
    """Fuse sources while preventing aliases from multiplying family influence."""

    if not sources:
        raise SynthesisValidationError("synthesis requires sources")
    if not 0.0 <= float(cost_probability) <= 0.5:
        raise SynthesisValidationError("cost_probability must be in [0, 0.5]")
    ids = tuple(source.agent_id for source in sources)
    if len(set(ids)) != len(ids):
        raise SynthesisValidationError("synthesis agent_ids contain duplicates")
    priors = tuple(
        source
        for source in sources
        if source.role == "market_prior" and source.family_id == "market-price"
    )
    if len(priors) != 1 or priors[0].stale:
        raise SynthesisValidationError("one fresh market-price prior is required")
    prior = priors[0]
    influence_caps = dict(family_influence_caps or {})
    if any(not 0.0 <= float(value) <= 1.0 for value in influence_caps.values()):
        raise SynthesisValidationError("shadow influence caps must be in [0, 1]")

    excluded: list[tuple[str, str]] = []
    active_non_market = []
    for source in sources:
        if source is prior:
            continue
        if source.stale:
            excluded.append((source.agent_id, "stale_source_zero_weight"))
            continue
        score = source.proposed_weight * source.regime_relevance * source.independence
        if score <= 0.0:
            excluded.append((source.agent_id, "zero_relevance_or_guard_cap"))
            continue
        active_non_market.append((source, score))

    family_scores: dict[str, float] = defaultdict(float)
    family_sources: dict[str, list[tuple[SynthesisSource, float]]] = defaultdict(list)
    for source, score in active_non_market:
        family_scores[source.family_id] += score
        family_sources[source.family_id].append((source, score))
    family_caps: dict[str, float] = {}
    for family_id, members in family_sources.items():
        all_uncalibrated = all(not source.calibrated for source, _ in members)
        base_cap = (
            policy.uncalibrated_advisory_cap
            if all_uncalibrated
            else policy.non_market_family_cap
        )
        family_caps[family_id] = min(
            base_cap,
            base_cap * influence_caps.get(family_id, 1.0),
        )

    market_weight = max(policy.market_prior_floor, prior.proposed_weight)
    market_weight = min(1.0, market_weight)
    family_allocations = _allocate_families(
        family_scores,
        family_caps,
        1.0 - market_weight,
    )
    allocated_non_market = sum(family_allocations.values())
    market_weight = round(1.0 - allocated_non_market, 12)
    if market_weight + 1e-12 < policy.market_prior_floor:
        raise SynthesisValidationError("market-prior floor was violated")

    source_weights: dict[str, float] = {prior.agent_id: market_weight}
    for family_id, allocation in family_allocations.items():
        members = family_sources[family_id]
        total = sum(score for _, score in members)
        for source, score in members:
            source_weights[source.agent_id] = allocation * score / total
    normalization = sum(source_weights.values())
    if normalization <= 0.0:
        raise SynthesisValidationError("synthesis produced no usable weight")
    source_weights = {
        key: value / normalization for key, value in source_weights.items()
    }
    by_id = {source.agent_id: source for source in sources}
    probability = sum(
        by_id[agent_id].probability_yes * weight
        for agent_id, weight in source_weights.items()
    )
    probability = round(min(1.0, max(0.0, probability)), 12)
    dispersion = math.sqrt(
        sum(
            weight * (by_id[agent_id].probability_yes - probability) ** 2
            for agent_id, weight in source_weights.items()
        )
    )
    base_uncertainty = max(
        by_id[agent_id].uncertainty for agent_id in source_weights
    )
    half_width = min(0.5, base_uncertainty + dispersion)
    interval = (
        round(max(0.0, probability - half_width), 12),
        round(min(1.0, probability + half_width), 12),
    )
    family_weights = {"market-price": source_weights[prior.agent_id]}
    for family_id, allocation in family_allocations.items():
        family_weights[family_id] = allocation / normalization
    non_market = tuple(by_id[key] for key in source_weights if key != prior.agent_id)
    calibrated_count = sum(source.calibrated for source in non_market)
    if non_market and calibrated_count == len(non_market):
        calibration_state = CalibrationState.FULLY_CALIBRATED
    elif calibrated_count:
        calibration_state = CalibrationState.PARTIALLY_CALIBRATED
    else:
        calibration_state = CalibrationState.UNCALIBRATED
    dominant = tuple(
        sorted(
            source.agent_id
            for source in sources
            if source_weights.get(source.agent_id, 0.0) >= 0.20
        )
    )
    counterevidence = tuple(
        sorted(
            source.agent_id
            for source in sources
            if source.agent_id in source_weights
            and (source.probability_yes - prior.probability_yes)
            * (probability - prior.probability_yes)
            < 0.0
        )
    )
    return SynthesisResult(
        probability_yes=probability,
        uncertainty_interval=interval,
        source_weights=tuple(source_weights.items()),
        family_weights=tuple(family_weights.items()),
        market_prior_probability=prior.probability_yes,
        market_prior_weight=source_weights[prior.agent_id],
        market_prior_floor=policy.market_prior_floor,
        edge_after_costs=round(
            abs(probability - prior.probability_yes) - float(cost_probability),
            12,
        ),
        calibration_state=calibration_state,
        dominant_evidence=dominant,
        counterevidence=counterevidence,
        excluded_sources=tuple(sorted(excluded)),
        policy_version=policy.policy_version,
    )
