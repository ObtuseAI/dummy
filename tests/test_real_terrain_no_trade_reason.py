from __future__ import annotations

from predator_mesh.v12.liquidity_v2 import LiveLiquidityProofEngineV2


def test_real_terrain_no_trade_reason_report_covers_liquidity_and_staleness() -> None:
    report = LiveLiquidityProofEngineV2().no_trade_reason_report()

    assert report["verdict"] == "PASS"
    assert "NO_TRADE_LIQUIDITY_TOO_THIN" in report["covered_reasons"]
    assert "NO_TRADE_STALE_ORDERBOOK" in report["covered_reasons"]
    assert "NO_TRADE_SPREAD_TOO_WIDE" in report["covered_reasons"]
