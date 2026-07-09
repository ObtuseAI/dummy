from tests.v27_test_helpers import assert_current_test_report


def test_dummy_mission_state_v27_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
    assert report["mission_state_verdict"] in {"PASS", "PARTIAL"}
    assert report["integration_mode_public_probe_controller_status"] == "PASS"
    assert report["integration_probes_enabled_status"] == "disabled_by_default"
    assert report["live_submit_flag_status"] == "enabled=false"
    assert report["live_scored_count"] >= 0
    assert report["partial_causes_remaining"]
