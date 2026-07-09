from __future__ import annotations

from predator_mesh.v11.orderbook import OrderbookLiquidityModel


def test_stale_quote_risk_detects_stale_book() -> None:
    model = OrderbookLiquidityModel()
    fresh = model.analyze(model.sample_orderbook(age_seconds=5))
    stale = model.analyze(model.sample_orderbook(age_seconds=90))

    assert fresh.stale_quote_risk.status == "FRESH"
    assert stale.stale_quote_risk.status == "STALE"
    assert stale.execution_feasibility_score.status == "NO_TRADE_STALE_ORDERBOOK"
