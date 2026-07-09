from __future__ import annotations

from tests.v45_test_helpers import v45_reports


def test_v45_reads_v44_pass_baseline_without_regression() -> None:
    report = v45_reports()["v44_baseline_readback_v1_report.json"]
    assert report["v44_baseline_status"] == "PASS_V44_BASELINE_READBACK"
    assert report["v44_carried_status"] == "PASS"
    assert report["v44_new_real_scored_count"] >= 18
    assert report["v44_cumulative_real_scored_count"] >= 45
    assert report["v44_cumulative_evidence_count"] >= 45
    assert report["sample_diversity_status"] == "PASS_SAMPLE_DIVERSITY"
    assert report["calibration_tier"] == "DEVELOPING_SAMPLE"
    assert report["execution_lock_v3_status"] == "PASS"
    assert report["execution_bridge_present"] is False
