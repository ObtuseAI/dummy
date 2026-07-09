from __future__ import annotations

import pytest

from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge
from predator_mesh.v13.orderbook_snapshot_v2 import RealKalshiOrderbookSnapshotAdapterV2


@pytest.mark.asyncio
async def test_orderbook_snapshot_mode_v2_marks_missing_credentials_partial_without_real_claim(tmp_path) -> None:
    bridge = KalshiReadOnlyCredentialBridge(
        env={},
        dummy_env_path=tmp_path / "missing_dummy.env",
        project_env_path=tmp_path / "missing_project.env",
    )

    closure = await RealKalshiOrderbookSnapshotAdapterV2(credential_bridge=bridge).capture()
    report = closure.mode_report()

    assert closure.outcome == "CREDENTIALS_MISSING"
    assert report["active_modes"] == ["SAMPLE_STATIC_FALLBACK"]
    assert report["verdict"] == "PARTIAL"
