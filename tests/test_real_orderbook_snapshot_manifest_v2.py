from __future__ import annotations

import json

from predator_mesh.v14.terrain_closure import RealOrderbookTerrainClosureV2
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_real_orderbook_snapshot_manifest_v2_is_sanitized_and_proof_backed() -> None:
    report = RealOrderbookTerrainClosureV2(forensics_report=fake_invalid_forensics_report()).snapshot_manifest()
    text = json.dumps(report)

    assert report["snapshot_count"] == 1
    assert report["snapshots"][0]["real_read_only"] is False
    assert report["snapshots"][0]["proof_ref"]
    assert "BEGIN PRIVATE KEY" not in text
