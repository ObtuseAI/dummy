from __future__ import annotations

from tests.v44_test_helpers import v44_enabled_reports


def test_dummy_mission_state_v44_tracks_scaleout_and_locks() -> None:
    mission = v44_enabled_reports()["dummy_mission_state_report_v30.json"]
    assert mission["v43_carried_status"] == "PASS"
    assert mission["v43_baseline_status"] == "PASS_V43_BASELINE_READBACK"
    assert mission["observer_scaleout_status"] == "PASS_READONLY_OBSERVER_SCALEOUT"
    assert mission["source_truth_v25_status"] == "PASS"
    assert mission["market_class_reliability_v5_status"] == "PASS"
    assert mission["readiness_governor_v4_status"] == "PASS"
    assert mission["execution_lock_v3_status"] == "PASS"
    assert mission["live_submit_disabled"] is True
    assert mission["caps_unchanged"] is True
    assert mission["no_execution_bridge_status"] == "PASS"
