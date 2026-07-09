from __future__ import annotations

from tests.v45_test_helpers import v45_enabled_reports


def test_dummy_mission_state_v45_tracks_continuation_and_locks() -> None:
    mission = v45_enabled_reports()["dummy_mission_state_report_v31.json"]
    assert mission["v44_carried_status"] == "PASS"
    assert mission["v44_baseline_status"] == "PASS_V44_BASELINE_READBACK"
    assert mission["observer_continuation_status"] == "PASS_READONLY_OBSERVER_CONTINUATION"
    assert mission["source_truth_v26_status"] == "PASS"
    assert mission["market_class_reliability_v6_status"] == "PASS"
    assert mission["stable_sample_prep_status"] == "LOCKED_INSUFFICIENT_100_REAL_SCORES"
    assert mission["readiness_governor_v5_status"] == "PASS"
    assert mission["execution_lock_v4_status"] == "PASS"
    assert mission["live_submit_disabled"] is True
    assert mission["caps_unchanged"] is True
    assert mission["no_execution_bridge_status"] == "PASS"
