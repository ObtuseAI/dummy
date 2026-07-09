from __future__ import annotations

from predator_mesh.v12.replay import OrderbookReplayRun


def test_liquidity_replay_consistency_flags_stale_or_malformed_frames() -> None:
    report = OrderbookReplayRun().consistency_report()

    assert report["verdict"] == "PASS"
    assert report["checks"]["monotonic_frame_index"] is True
    assert report["checks"]["malformed_frames_rejected"] is True
    assert report["checks"]["stale_frames_detected"] is True
