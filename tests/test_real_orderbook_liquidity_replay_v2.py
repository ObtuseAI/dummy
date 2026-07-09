from __future__ import annotations

from predator_mesh.v13.replay_v2 import RealOrderbookReplayStore
from tests.v13_test_helpers import real_snapshot_result


def test_real_orderbook_liquidity_replay_v2_uses_real_terrain_frame() -> None:
    store = RealOrderbookReplayStore()
    store.add_snapshot(real_snapshot_result())

    report = store.to_report()

    assert report["frame_count"] == 1
    assert report["real_terrain_used"] is True
    assert report["verdict"] == "PASS"
