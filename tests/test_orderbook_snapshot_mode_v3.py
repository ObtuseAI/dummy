from __future__ import annotations

from predator_mesh.v14.terrain_closure import RealOrderbookTerrainClosureV2
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_orderbook_snapshot_mode_v3_counts_sample_fallback_without_real_claim() -> None:
    report = RealOrderbookTerrainClosureV2(forensics_report=fake_invalid_forensics_report()).snapshot_mode_report()

    assert report["active_modes"] == ["SAMPLE_STATIC_FALLBACK"]
    assert report["terrain_mode"] == "PARTIAL_CREDENTIALS_INVALID"
    assert report["verdict"] == "PARTIAL"
