from __future__ import annotations

from predator_mesh.v11.post_trade import PostTradeLedgerSkeleton


def test_post_trade_ledger_skeleton_uses_simulated_fills_only() -> None:
    report = PostTradeLedgerSkeleton().to_report()

    assert report["verdict"] == "PASS"
    assert report["records"]
    assert report["records"][0]["simulated_only"] is True
    assert report["records"][0]["liquidity_proof_refs"]
