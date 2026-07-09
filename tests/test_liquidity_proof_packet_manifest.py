from __future__ import annotations

from predator_mesh.v11.liquidity import LiveLiquidityProofEngine


def test_liquidity_proof_packet_manifest_contains_proof_refs() -> None:
    manifest = LiveLiquidityProofEngine().packet_manifest()

    assert manifest["verdict"] == "PASS"
    assert manifest["packets"]
    for packet in manifest["packets"]:
        assert packet["packet_id"]
        assert packet["proof_refs"]["edge_candidate"]
        assert packet["execution_terrain"]["limit_order_only"] is True
        assert packet["live_submit_required"] is False
