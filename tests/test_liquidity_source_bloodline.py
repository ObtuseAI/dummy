from __future__ import annotations

from predator_mesh.v12.bloodline import LiquiditySourceBloodline


def test_liquidity_source_bloodline_scores_orderbook_reliability() -> None:
    report = LiquiditySourceBloodline().to_report()

    assert report["verdict"] == "PASS"
    assert report["sources"][0]["source_name"] == "kalshi_real_orderbook_liquidity"
    assert 0 <= report["sources"][0]["orderbook_source_reliability"] <= 1
    assert report["sources"][0]["promotion_decision"] in {"PROMOTE", "WATCH", "KEEP_FALLBACK"}
