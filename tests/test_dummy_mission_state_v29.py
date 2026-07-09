from tests.v29_test_helpers import assert_current_test_report


def test_dummy_mission_state_v29_records_expected_partial_state_and_v28_reconciliation() -> None:
    report = assert_current_test_report(__file__)

    assert report["mission_state_verdict"] == "PARTIAL"
    assert report["v17_truth_loop_status"] == "PASS"
    assert report["v21_source_activation_status"] == "PASS"
    assert report["v22_forecast_write_status"] == "PASS"
    assert report["v28_oss_observation_closure_status"] == "PASS_PARTIAL_EXPECTED"
    assert report["total_candidate_count"] >= 246
    assert report["candidate_count_reconciliation_status"] == "RECONCILED_TO_CURRENT_V28_ARTIFACT"
    assert report["adapter_spec_factory_status"] == "PASS"
    assert report["public_probe_readiness_status"] == "PASS"
    assert report["integration_mode_status"] == "DISABLED_BY_DEFAULT"
    assert report["live_scored_count"] == 0
    assert report["live_unresolved_count"] == 3
    assert report["observed_forecast_count"] == 0
