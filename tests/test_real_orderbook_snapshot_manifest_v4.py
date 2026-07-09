from __future__ import annotations

from tests.v16_test_helpers import real_snapshot


def test_real_orderbook_snapshot_manifest_v4_tracks_snapshot_source() -> None:
    manifest = real_snapshot().manifest()

    assert manifest["version"] == "v4"
    assert manifest["snapshot_count"] == 1
    assert manifest["snapshots"][0]["snapshot_mode"] == "REAL_READ_ONLY"
    assert manifest["sanitized"] is True
