from __future__ import annotations


def test_dummy_mission_state_v17_summarizes_truth_loop() -> None:
    from predator_mesh.v17.mission_state import DummyMissionStateV17

    report = DummyMissionStateV17().to_report()

    assert report["outcome_ledger_status"] == "PASS"
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
