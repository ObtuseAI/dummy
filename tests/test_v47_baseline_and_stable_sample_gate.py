from __future__ import annotations

from tests.v47_test_helpers import assert_v47_report_named


def test_v46_baseline_readback_v1_preserves_passed_81_score_authority() -> None:
    report = assert_v47_report_named("v46_baseline_readback_v1_report.json", "v46_baseline_status")
    assert report["v46_baseline_status"] == "PASS_V46_BASELINE_READBACK"
    assert report["v46_final_verdict"] == "PASS"
    assert report["v46_cumulative_evidence_count"] >= 81
    assert report["v46_cumulative_real_scored_count"] >= 81
    assert report["v46_score_gap_to_100"] == 19
    assert report["v46_stable_sample_status"] == "LOCKED_INSUFFICIENT_100_REAL_SCORES"


def test_v47_stable_sample_gate_requires_100_scores_and_all_quality_gates() -> None:
    locked = assert_v47_report_named("v47_stable_sample_candidate_gate_report.json", "stable_sample_candidate_status")
    assert locked["stable_sample_candidate_status"] == "LOCKED_INSUFFICIENT_100_REAL_SCORES"
    assert locked["stable_sample_candidate_unlocked"] is False

    reviewed = assert_v47_report_named(
        "v47_stable_sample_candidate_gate_report.json",
        "stable_sample_candidate_status",
        enabled=True,
    )
    assert reviewed["stable_sample_candidate_status"] == "STABLE_SAMPLE_CANDIDATE_REVIEW_READONLY"
    assert reviewed["stable_sample_quality_status"] == "PASS"
    assert reviewed["sample_quality_status"] == "PASS_SAMPLE_QUALITY"
    assert reviewed["sample_diversity_status"] == "PASS_SAMPLE_DIVERSITY"
    assert reviewed["temporal_spread_status"] == "PASS_TEMPORAL_SPREAD"
    assert reviewed["metric_cluster_status"] == "PASS_METRIC_CLUSTER_CONTROL"
    assert reviewed["source_concentration_status"] == "PASS_SOURCE_CONCENTRATION_CONTROL"
    assert reviewed["calibration_drift_status"] == "PASS_NO_MATERIAL_DRIFT_DETECTED_DIAGNOSTIC"
