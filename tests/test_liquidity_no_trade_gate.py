from __future__ import annotations

from predator_mesh.v14.no_trade_gates import LiquidityNoTradeGate
from tests.v14_test_helpers import fake_invalid_forensics_report


def test_liquidity_no_trade_gate_blocks_invalid_real_terrain() -> None:
    report = LiquidityNoTradeGate(forensics_report=fake_invalid_forensics_report()).to_report()

    assert report["trade_allowed"] is False
    assert "CREDENTIALS_INVALID" in report["no_trade_reasons"]
    assert "REAL_TERRAIN_NOT_PROVEN" in report["no_trade_reasons"]
    assert report["verdict"] == "PASS"
