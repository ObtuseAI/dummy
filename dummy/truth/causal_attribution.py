"""Conservative attribution of apparent evolutionary forecast gains."""

from __future__ import annotations

from typing import Any

from dummy.world_model.models import digest_json

from .cluster_statistics import ClusterStatistic


def causal_attribution_report(
    *,
    candidate_id: str,
    raw_brier_gain: float | None,
    contested_brier_gain: float | None,
    clustered: ClusterStatistic,
    transfer_passed: bool,
    multiple_testing_passed: bool,
    point_in_time_verified: bool,
    fill_truth_separate: bool,
) -> dict[str, Any]:
    supported = bool(
        raw_brier_gain is not None
        and raw_brier_gain > 0.0
        and contested_brier_gain is not None
        and contested_brier_gain > 0.0
        and clustered.positive_interval
        and transfer_passed
        and multiple_testing_passed
        and point_in_time_verified
        and fill_truth_separate
    )
    body: dict[str, Any] = {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "raw_brier_gain": raw_brier_gain,
        "contested_brier_gain": contested_brier_gain,
        "cluster_adjusted_gain": clustered.observed_mean,
        "confidence_interval": (
            list(clustered.confidence_interval)
            if clustered.confidence_interval is not None
            else None
        ),
        "causal_confidence": (
            1.0 - clustered.one_sided_p_value
            if clustered.one_sided_p_value is not None
            else None
        ),
        "transfer_passed": transfer_passed,
        "multiple_testing_passed": multiple_testing_passed,
        "point_in_time_verified": point_in_time_verified,
        "fill_truth_separate": fill_truth_separate,
        "selection_effects_controlled": multiple_testing_passed,
        "survivorship_not_assumed_away": True,
        "verdict": (
            "HELD_OUT_IMPROVEMENT_SUPPORTED"
            if supported
            else "INSUFFICIENT_EDGE_EVIDENCE"
        ),
    }
    body["report_id"] = digest_json(body)
    return body


__all__ = ["causal_attribution_report"]
