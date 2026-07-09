from __future__ import annotations

from tests.v44_test_helpers import v44_reports


def test_v44_reads_v43_pass_baseline_without_regression() -> None:
    report = v44_reports()["v43_baseline_readback_v1_report.json"]
    assert report["v43_baseline_status"] == "PASS_V43_BASELINE_READBACK"
    assert report["v43_carried_status"] == "PASS"
    assert report["v43_new_real_scored_count"] >= 9
    assert report["v43_cumulative_real_scored_count"] >= 27
    assert report["v43_cumulative_evidence_count"] >= 27
    assert report["calibration_tier"] == "DEVELOPING_SAMPLE"
    assert report["execution_lock_v2_status"] == "PASS"
    assert report["execution_bridge_present"] is False
