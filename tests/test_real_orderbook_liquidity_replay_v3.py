from __future__ import annotations

from predator_mesh.v14.terrain_closure import RealOrderbookTerrainClosureV2
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_real_orderbook_liquidity_replay_v3_marks_sample_fallback_partial() -> None:
    report = RealOrderbookTerrainClosureV2(forensics_report=fake_invalid_forensics_report()).replay_report()

    assert report["real_terrain_used"] is False
    assert report["terrain_mode"] == "PARTIAL_CREDENTIALS_INVALID"
    assert report["verdict"] == "PARTIAL"
