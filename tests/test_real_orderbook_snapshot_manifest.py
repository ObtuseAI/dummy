from __future__ import annotations

import json

import pytest

from predator_mesh.v13.orderbook_snapshot_v2 import RealKalshiOrderbookSnapshotAdapterV2
from tests.v13_test_helpers import FakeRealKalshiReadOnlyClient, SECRET_KEY, SECRET_PEM, ready_bridge


@pytest.mark.asyncio
async def test_real_orderbook_snapshot_manifest_is_sanitized(tmp_path) -> None:
    closure = await RealKalshiOrderbookSnapshotAdapterV2(
        credential_bridge=ready_bridge(tmp_path),
        read_only_client_factory=FakeRealKalshiReadOnlyClient,
    ).capture()

    manifest = closure.manifest()
    text = json.dumps(manifest)
    assert manifest["snapshot_count"] == 1
    assert manifest["snapshots"][0]["real_read_only"] is True
    assert SECRET_KEY not in text
    assert SECRET_PEM not in text
