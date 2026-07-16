"""Replication and theory gates for reusable cognitive knowledge."""

from __future__ import annotations

from collections.abc import Iterable

from dummy.world_model.models import digest_json

from .models import ReplicationReceipt, TheoryMaturity


def evaluate_theory(
    *,
    hypothesis_id: str,
    claim: str,
    receipts: Iterable[ReplicationReceipt],
) -> dict[str, object]:
    """Evaluate maturity without allowing weak evidence to become a 'law'."""
    matching = tuple(
        sorted(
            (item for item in receipts if item.hypothesis_id == hypothesis_id),
            key=lambda item: item.receipt_id,
        )
    )
    valid = tuple(
        item
        for item in matching
        if item.effect_lower_bound > 0.0
        and item.calibration_noninferior
        and item.deterministic_replay
        and item.reward_hack_free
        and item.fixed_cost_noninferior
        and item.future_leakage_free
        and item.forced_coverage_free
        and item.source_correlation_free
        and item.execution_truth_noninferior
        and item.complexity_noninferior
    )
    domains = {item.domain_id for item in valid}
    independence_keys = {item.independence_key for item in valid}
    if matching and not valid:
        maturity = TheoryMaturity.REJECTED
    elif len(valid) >= 6 and len(domains) >= 3 and len(independence_keys) >= 6:
        maturity = TheoryMaturity.GENERAL_LAW
    elif len(valid) >= 3 and len(domains) >= 2 and len(independence_keys) >= 3:
        maturity = TheoryMaturity.PROVISIONAL_THEORY
    else:
        maturity = TheoryMaturity.HYPOTHESIS
    body: dict[str, object] = {
        "schema_version": 1,
        "hypothesis_id": hypothesis_id,
        "claim": claim,
        "maturity": maturity.value,
        "matching_replications": len(matching),
        "valid_replications": len(valid),
        "independent_domains": sorted(domains),
        "independence_keys": sorted(independence_keys),
        "valid_receipt_ids": [item.receipt_id for item in valid],
        "gates": {
            "no_future_leakage": bool(valid) and all(item.future_leakage_free for item in valid),
            "no_forced_coverage_contamination": bool(valid) and all(item.forced_coverage_free for item in valid),
            "source_correlation_free": bool(valid) and all(item.source_correlation_free for item in valid),
            "execution_truth_noninferior": bool(valid) and all(item.execution_truth_noninferior for item in valid),
            "complexity_noninferior": bool(valid) and all(item.complexity_noninferior for item in valid),
            "calibration_noninferior": bool(valid) and all(item.calibration_noninferior for item in valid),
            "deterministic_replay": bool(valid) and all(item.deterministic_replay for item in valid),
            "reward_hack_free": bool(valid) and all(item.reward_hack_free for item in valid),
            "fixed_cost_noninferior": bool(valid) and all(item.fixed_cost_noninferior for item in valid),
            "provisional_requires_three_replications_two_domains": True,
            "law_requires_six_replications_three_domains": True,
        },
        "automatic_promotion": False,
        "authority": "OBSERVE_AND_RECOMMEND_ONLY",
    }
    body["theory_id"] = digest_json(body)
    return body


__all__ = ["evaluate_theory"]
