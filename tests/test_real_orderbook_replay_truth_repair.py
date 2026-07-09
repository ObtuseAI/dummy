from __future__ import annotations

from tests.v16_test_helpers import real_snapshot


def test_replay_truth_repair_consumes_real_snapshot_by_default() -> None:
    from predator_mesh.v16.replay_truth import RealOrderbookReplayTruthRepair

    report = RealOrderbookReplayTruthRepair(snapshot_result=real_snapshot()).to_report()

    assert report["input_mode"] == "REAL_SNAPSHOT_REPLAY"
    assert report["frame_count"] == 1
    assert report["fallback_reason"] == ""
