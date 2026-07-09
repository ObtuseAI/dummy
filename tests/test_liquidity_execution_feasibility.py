from __future__ import annotations

from predator_mesh.v12.orderbook_v2 import OrderbookLiquidityModelV2


def test_liquidity_execution_feasibility_report_is_bounded() -> None:
    report = OrderbookLiquidityModelV2().execution_feasibility_report()

    assert report["verdict"] == "PASS"
    assert 0 <= report["execution_feasibility_score"]["total"] <= 1
    assert report["max_request_timeout_s"] <= 10
    assert report["max_adapter_timeout_s"] <= 45
