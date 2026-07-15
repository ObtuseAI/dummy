"""Proposal-only meta-policy challenger contract; no automatic application."""

from __future__ import annotations

from typing import Mapping


def meta_policy_proposal(
    *,
    baseline_policy_version: str,
    proposed_changes: Mapping[str, object],
    evidence_ids: tuple[str, ...],
) -> dict[str, object]:
    return {
        "baseline_policy_version": baseline_policy_version,
        "proposed_changes": dict(sorted(proposed_changes.items())),
        "evidence_ids": sorted(evidence_ids),
        "applied": False,
        "automatic_promotion": False,
        "authority": "RECOMMEND_ONLY",
        "required_gates": [
            "held_out_event_clusters",
            "cross_market_transfer",
            "calibration_improvement",
            "no_governance_regression",
            "deterministic_replay",
            "human_review",
        ],
    }
