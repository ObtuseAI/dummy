from __future__ import annotations

from predator_mesh.v14.terrain_closure import RealOrderbookTerrainClosureV2
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_fill_quality_estimate_v4_is_present_even_when_real_terrain_blocked() -> None:
    report = RealOrderbookTerrainClosureV2(forensics_report=fake_invalid_forensics_report()).fill_quality_report()

    assert report["terrain_mode"] == "PARTIAL_CREDENTIALS_INVALID"
    assert "estimate" in report
    assert report["verdict"] == "PARTIAL"
