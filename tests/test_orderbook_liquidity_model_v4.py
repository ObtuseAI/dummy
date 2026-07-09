from __future__ import annotations

from predator_mesh.v14.terrain_closure import RealOrderbookTerrainClosureV2
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_orderbook_liquidity_model_v4_reports_credentials_invalid_terrain_mode() -> None:
    report = RealOrderbookTerrainClosureV2(forensics_report=fake_invalid_forensics_report()).liquidity_model_report()

    assert report["terrain_mode"] == "PARTIAL_CREDENTIALS_INVALID"
    assert report["verdict"] == "PARTIAL"
