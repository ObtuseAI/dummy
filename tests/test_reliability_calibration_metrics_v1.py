from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_reliability_calibration_metrics_v1_is_diagnostic_only() -> None:
    report = assert_current_test_report(__file__)
    assert report["calibration_metrics_status"] == "PASS"
    assert report["metric_mode"] == "EARLY_SAMPLE_DIAGNOSTIC_ONLY"
    assert report["pnl_claim_made"] is False
    assert report["trading_edge_claim_made"] is False
