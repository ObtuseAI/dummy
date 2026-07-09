from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_v41_baseline_readback_v1_preserves_v41_pass_counts() -> None:
    report = assert_current_test_report(__file__)
    assert report["v41_baseline_readback_v1_status"] == "PASS_V41_BASELINE_READBACK"
    assert report["v41_cumulative_real_scored_count"] >= 12
    assert report["v41_cumulative_evidence_count"] >= 12
    assert report["v41_new_real_scored_count"] >= 6
    assert report["v41_source_truth_v22_status"] == "PASS"
    assert report["v41_readiness_ladder_status"] == "PASS"
