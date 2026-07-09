from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_dummy_mission_state_v18_summarizes_source_truth_and_live_safety() -> None:
    from predator_mesh.v18.mission import DummyMissionStateV18

    report = DummyMissionStateV18().to_report()

    assert_pass_report(report)
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["no_direct_order_cancel_bypass"] is True
    assert report["fixture_evidence_claimed_real"] is False
