from __future__ import annotations

import pytest

from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge
from predator_mesh.v13.market_discovery import MarketDiscoveryMode, RealKalshiMarketDiscovery


@pytest.mark.asyncio
async def test_market_discovery_modes_do_not_fake_real_when_credentials_missing(tmp_path) -> None:
    bridge = KalshiReadOnlyCredentialBridge(
        env={},
        dummy_env_path=tmp_path / "missing_dummy.env",
        project_env_path=tmp_path / "missing_project.env",
    )

    proof = await RealKalshiMarketDiscovery(credential_bridge=bridge).discover()

    assert proof.mode is MarketDiscoveryMode.SAMPLE_STATIC_FALLBACK
    assert proof.degradation_reason == "CREDENTIALS_MISSING"
    assert proof.real_read_only_used is False
    assert proof.to_mode_report()["verdict"] == "PARTIAL"
