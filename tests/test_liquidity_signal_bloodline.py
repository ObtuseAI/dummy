from __future__ import annotations

from predator_mesh.v12.bloodline import LiquiditySignalBloodline


def test_liquidity_signal_bloodline_tracks_spread_depth_stale_fill_drag_usefulness() -> None:
    report = LiquiditySignalBloodline().to_report()

    assert report["verdict"] == "PASS"
    signal_names = {signal["signal_name"] for signal in report["signals"]}
    assert {"spread", "depth", "stale_quote", "fill_drag", "no_trade_pressure"}.issubset(signal_names)
