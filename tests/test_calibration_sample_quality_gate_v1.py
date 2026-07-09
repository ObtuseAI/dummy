from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report, v42_enabled_reports


def test_calibration_sample_quality_gate_v1_measures_quality_without_invalid_samples() -> None:
    report = assert_current_test_report(__file__)
    assert report["sample_quality_status"] == "PASS_BASELINE_QUALITY"
    assert report["duplicate_evidence_inflated_sample_count"] is False
    enabled = v42_enabled_reports()["calibration_sample_quality_gate_v1_report.json"]
    assert enabled["sample_quality_status"] == "PASS_SAMPLE_QUALITY"
    assert enabled["freshness_pass_rate"] == 1.0
    assert enabled["score_eligibility_rate"] == 1.0
