from __future__ import annotations

from tests.v16_test_helpers import real_snapshot


def test_real_orderbook_liquidity_replay_v5_reports_depth_spread_and_fill_drag() -> None:
    from predator_mesh.v16.replay_truth import RealOrderbookReplayTruthRepair

    report = RealOrderbookReplayTruthRepair(snapshot_result=real_snapshot()).liquidity_replay_report_v5()

    assert report["input_mode"] == "REAL_SNAPSHOT_REPLAY"
    assert report["frames"][0]["depth"] > 0
    assert "fill_drag" in report["frames"][0]
