from __future__ import annotations

from decimal import Decimal
from typing import Optional

from core.ontology import ComplianceVerdict, EdgeEstimate, Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class OrderbookSpreadCaptureStrategy(StrategyGenome):
    """Repo-derived orderbook spread capture strategy.

    Watches orderbook updates and emits a TradeProposal when spread capture meets
    caps. Never calls live order endpoints.
    """

    name = "orderbook_spread_capture"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        """Return a TradeProposal when orderbook spread capture is favorable.

        No-trade cases:
        - Probability delta is too small.
        - Edge after fees is non-positive.
        - Confidence is below the strategy threshold.
        - Settlement risk is elevated.
        - Orderbook lacks liquidity or quotes are stale/wide.
        - Spread is too wide to capture.
        """
        if not orderbook.bids or not orderbook.asks:
            return None  # no-trade: missing orderbook liquidity

        spread = orderbook.asks[0].price - orderbook.bids[0].price
        total_liquidity = sum(level.size for level in orderbook.bids) + sum(level.size for level in orderbook.asks)

        if abs(forecast.probability_delta) <= Decimal("0.02"):
            return None  # no-trade: probability divergence too small
        if forecast.edge_after_fees <= Decimal("0.004"):
            return None  # no-trade: edge after fees insufficient
        if forecast.confidence_score < Decimal("0.6"):
            return None  # no-trade: spread-capture confidence too low
        if forecast.settlement_risk_score > Decimal("0.55"):
            return None  # no-trade: elevated settlement risk
        if spread > 4:
            return None  # no-trade: spread too wide to capture
        if total_liquidity < 12:
            return None  # no-trade: insufficient liquidity

        side = "yes" if forecast.probability_delta > 0 else "no"
        price = int(orderbook.asks[0].price) if side == "yes" else int(100 - orderbook.bids[0].price)
        size = 1
        order_value = price * size

        edge_bps = int(forecast.expected_edge * Decimal(10000))
        edge_after_fees_bps = int(forecast.edge_after_fees * Decimal(10000))

        return TradeProposal(
            id=f"{self.name}_{forecast.market_ticker}_{forecast.contract_ticker}",
            market_ticker=forecast.market_ticker,
            contract_ticker=forecast.contract_ticker,
            side=side,
            price_cents=price,
            size=size,
            forecast_reference=forecast.proof_reference,
            edge_estimate=EdgeEstimate(
                expected_edge_bps=edge_bps,
                edge_after_fees_bps=edge_after_fees_bps,
                confidence_score=forecast.confidence_score,
            ),
            risk_estimate=(
                f"liquidity={total_liquidity} spread={spread}c "
                f"settlement_risk={forecast.settlement_risk_score} spread_capture_confidence={forecast.confidence_score}"
            ),
            confidence_estimate=forecast.confidence_score,
            expected_fill_behavior="passive limit fill capturing inside spread within 30s",
            stop_condition="spread widens beyond capture threshold",
            cancellation_condition="orderbook stale > 30s or spread capture edge evaporates",
            cap_impact={
                "estimated_order_value_cents": order_value,
                "max_single_order_cents": order_value,
                "liquidity_estimate": total_liquidity,
                "spread_estimate_cents": spread,
                "settlement_risk_estimate": float(forecast.settlement_risk_score),
            },
            compliance_verdict=ComplianceVerdict(
                passed=True,
                blocked_categories=[],
                reason="Orderbook spread-capture repo-derived strategy emits TradeProposal only; no live order path",
            ),
            proof_reference=f"strategy:{self.name}|forecast:{forecast.proof_reference}",
        )
