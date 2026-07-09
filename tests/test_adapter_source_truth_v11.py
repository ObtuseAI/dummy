from tests.v30_test_helpers import assert_v30_report_named


def test_adapter_source_truth_v11_reports_fixture_truth_without_live_claims() -> None:
    report = assert_v30_report_named("adapter_source_truth_v11_report.json", "adapter_source_truth_v11_status")

    assert report["adapter_source_truth_v11_status"] == "PASS"
    assert report["adapter_implementation_truth_signal"] == "IMPLEMENTED_FIXTURE_CONTRACTS"
    assert report["adapter_fixture_truth_signal"] == "FIXTURE_NOT_LIVE"
    assert report["adapter_normalization_truth_signal"] == "NORMALIZED_PIPELINE_ONLY"
    assert report["adapter_settlement_truth_signal"] == "SETTLEMENT_COMPATIBLE_PIPELINE_ONLY"
    assert report["source_truth_to_execution_bridge_present"] is False
