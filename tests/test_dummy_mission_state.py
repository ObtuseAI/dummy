from __future__ import annotations

from tests.v16_test_helpers import pass_truth_verdict


def test_dummy_mission_state_summarizes_real_terrain_and_safety_flags() -> None:
    from predator_mesh.v16.mission_state import DummyMissionState

    report = DummyMissionState.from_truth(pass_truth_verdict()).to_report()

    assert report["terrain_truth_verdict"] == "PASS_REAL_TERRAIN"
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["no_direct_order_cancel_bypass"] is True
