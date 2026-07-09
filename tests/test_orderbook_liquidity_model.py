from __future__ import annotations

from predator_mesh.v11.orderbook import OrderbookLiquidityModel


def test_orderbook_liquidity_model_computes_depth_and_spread() -> None:
    analysis = OrderbookLiquidityModel().analyze(OrderbookLiquidityModel.sample_orderbook())

    assert analysis.depth_profile.best_bid == 48
    assert analysis.depth_profile.best_ask == 52
    assert analysis.spread_profile.spread_absolute == 4
    assert analysis.spread_profile.midpoint == 50
    assert analysis.depth_profile.top_of_book_depth == 220
    assert analysis.execution_feasibility_score.total > 0.5


def test_orderbook_liquidity_model_handles_empty_book() -> None:
    analysis = OrderbookLiquidityModel().analyze({"bids": [], "asks": []})

    assert analysis.execution_feasibility_score.status == "NO_TRADE_LIQUIDITY_TOO_THIN"
    assert analysis.fill_quality.expected_fill_probability.probability == 0
