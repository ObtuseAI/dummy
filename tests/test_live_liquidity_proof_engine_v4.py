from __future__ import annotations

from predator_mesh.v14.terrain_closure import RealOrderbookTerrainClosureV2
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_live_liquidity_proof_engine_v4_never_requires_live_submit() -> None:
    report = RealOrderbookTerrainClosureV2(forensics_report=fake_invalid_forensics_report()).live_liquidity_report()

    assert report["live_submit_required"] is False
    assert report["real_submit_calls"] == 0
    assert report["real_cancel_calls"] == 0
