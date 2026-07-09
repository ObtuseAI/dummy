from __future__ import annotations

from predator_mesh.v13.replay_v2 import RealOrderbookReplayQualityScore, RealOrderbookReplayStore
from tests.v13_test_helpers import real_snapshot_result


def test_liquidity_replay_quality_scores_real_frames_and_duplicates() -> None:
    store = RealOrderbookReplayStore()
    snapshot = real_snapshot_result()
    store.add_snapshot(snapshot)
    store.add_snapshot(snapshot)

    report = RealOrderbookReplayQualityScore(store).to_report()

    assert report["frame_count"] == 2
    assert report["duplicate_frames_detected"] >= 1
    assert report["quality_score"] >= 0
    assert report["verdict"] == "PASS"
