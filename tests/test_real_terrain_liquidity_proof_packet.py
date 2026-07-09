from __future__ import annotations

from predator_mesh.v12.liquidity_v2 import LiveLiquidityProofEngineV2


def test_real_terrain_liquidity_proof_packet_manifest_is_rehearsal_only() -> None:
    manifest = LiveLiquidityProofEngineV2().packet_manifest()

    assert manifest["verdict"] == "PASS"
    assert manifest["packets"][0]["live_submit_required"] is False
    assert manifest["packets"][0]["market_orders_allowed"] is False
    assert manifest["packets"][0]["firewall_rehearsal_status"] == "BLOCKED_LIVE_SUBMIT_DISABLED"
