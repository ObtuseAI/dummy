from __future__ import annotations

from predator_mesh.v14.terrain_closure import RealOrderbookTerrainClosureV2
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_real_orderbook_snapshot_adapter_v3_keeps_fallback_explicit_when_credentials_invalid() -> None:
    report = RealOrderbookTerrainClosureV2(forensics_report=fake_invalid_forensics_report()).snapshot_report()

    assert report["outcome"] == "CREDENTIALS_INVALID"
    assert report["snapshot_mode"] == "SAMPLE_STATIC_FALLBACK"
    assert report["real_orderbook_used"] is False
    assert report["verdict"] == "PARTIAL"
