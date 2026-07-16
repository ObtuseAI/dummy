from __future__ import annotations


def test_v17_truth_loop_still_passes_v20() -> None:
    from predator_mesh.v20.mission import DummyMissionStateV6

    assert DummyMissionStateV6().to_report()["v17_truth_loop_status"] == "PASS"
