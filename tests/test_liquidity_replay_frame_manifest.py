from __future__ import annotations

from predator_mesh.v12.replay import OrderbookReplayRun


def test_liquidity_replay_frame_manifest_contains_proof_refs() -> None:
    manifest = OrderbookReplayRun().frame_manifest()

    assert manifest["verdict"] == "PASS"
    assert manifest["frame_count"] >= 1
    assert manifest["frames"][0]["proof_ref"]
    assert "stale_quote_risk" in manifest["frames"][0]
