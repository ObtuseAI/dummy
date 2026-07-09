from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report


def test_v39_baseline_readback_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["v39_baseline_status"] == "PASS_V39_BASELINE_READBACK"
    assert report["baseline_real_probe_run_count"] >= 3
    assert report["baseline_real_evidence_count"] >= 3
    assert report["baseline_settlement_compatible_count"] >= 3
    assert report["baseline_real_observed_count"] >= 3
    assert report["baseline_real_scored_count"] >= 3
    assert report["v39_first_live_score_milestone_status"] == "PASS_FIRST_REAL_LIVE_PUBLIC_SCORE"
