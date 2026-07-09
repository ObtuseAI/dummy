from tests.v26_test_helpers import assert_current_test_report


def test_dummy_mission_state_v26_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
    assert report["mission_state_verdict"] in {"PASS", "PARTIAL"}
    assert report["keyless_public_adapter_registry_status"] == "PASS"
    assert report["keyless_adapter_active_count"] >= 8
    assert report["live_submit_flag_status"] == "enabled=false"
    assert report["live_scored_count"] >= 0
    assert report["next_bundle_recommendation"]
