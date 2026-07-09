from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_source_truth_v16_qc_and_sample_readiness_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["v34_qc_passed"] is True
    assert report["dispatch_overlap_fix_verified"] is True
    assert report["dead_constants_removed"] is True
    assert report["evidence_mode"] == "FAKE_TRANSPORT_TEST"
    assert report["frontend_build_passed"] is True
    assert report["sample_readiness"] == "PIPELINE_SCORE_ONLY"
    assert report["execution_bridge_present"] is False


def test_source_truth_qc_signal_passes() -> None:
    from tests.v35_test_helpers import assert_v35_report_named

    report = assert_v35_report_named("source_truth_qc_signal_report.json")
    assert report["signal"] == "V34_QC_PASSED"
