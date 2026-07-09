from __future__ import annotations

from predator_mesh.v14.terrain_closure import RealOrderbookTerrainClosureV2


def test_stale_quote_risk_v4_preserves_fresh_and_stale_detection() -> None:
    report = RealOrderbookTerrainClosureV2().stale_quote_report()

    assert report["fresh"]["status"] == "FRESH"
    assert report["stale"]["status"] == "STALE"
    assert report["verdict"] == "PASS"
