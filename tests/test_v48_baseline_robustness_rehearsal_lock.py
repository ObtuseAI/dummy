from __future__ import annotations

from tests.v48_test_helpers import assert_v48_report_named


def test_v47_baseline_readback_preserves_stable_sample_review_authority() -> None:
    report = assert_v48_report_named("v47_baseline_readback_v1_report.json", "v47_baseline_status")
    assert report["v47_baseline_status"] == "PASS_V47_BASELINE_READBACK"
    assert report["v47_final_verdict"] == "PASS"
    assert report["v47_cumulative_evidence_count"] >= 108
    assert report["v47_cumulative_real_scored_count"] >= 108
    assert report["v47_stable_sample_candidate_status"] == "STABLE_SAMPLE_CANDIDATE_REVIEW_READONLY"


def test_v48_robustness_review_audits_stable_sample_without_edge_claims() -> None:
    report = assert_v48_report_named("v48_robustness_review_report.json", "robustness_review_status", enabled=True)
    assert report["robustness_review_status"] == "PASS"
    assert report["source_concentration_review_status"] == "PASS"
    assert report["metric_cluster_review_status"] == "PASS"
    assert report["temporal_spread_review_status"] == "PASS"
    assert report["duplicate_stale_leakage_status"] == "PASS_NONE_DETECTED"
    assert report["statistically_final_edge_claim"] is False
    assert report["pnl_claim"] is False


def test_v48_locked_rehearsal_gate_design_is_design_only() -> None:
    report = assert_v48_report_named("v48_locked_rehearsal_gate_design_report.json", "locked_rehearsal_gate_design_status", enabled=True)
    assert report["locked_rehearsal_gate_design_status"] == "PASS_LOCKED_DESIGN_ONLY"
    assert report["future_operator_approval_phrase_required"] is True
    assert report["requires_kill_switch"] is True
    assert report["requires_cancel_reconcile_proof"] is True
    assert report["requires_fail_closed_behavior"] is True
    assert report["v48_rehearsal_artifacts_created"] is False
    assert report["execution_bridge_present"] is False
