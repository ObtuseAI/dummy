from decimal import Decimal
from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal, EdgeEstimate
from strategies.genome_base import StrategyGenome
from compliance.governor import assess_compliance


class ProbabilityDisagreement(StrategyGenome):
    name = "probability_disagreement"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        if abs(forecast.probability_delta) <= Decimal("0.02"):
            return None  # no-trade: edge too small
        compliance = assess_compliance(forecast.market_ticker, forecast.contract_ticker)
        if not compliance.passed:
            return None  # no-trade: compliance gate failed
        if not orderbook.asks or not orderbook.bids:
            return None  # no-trade: missing orderbook liquidity
        side = "yes" if forecast.probability_delta > 0 else "no"
        price = int(orderbook.asks[0].price) if side == "yes" else int(100 - orderbook.bids[-1].price)
        expected_edge_bps = int(abs(forecast.expected_edge) * Decimal("10000"))
        edge_after_fees_bps = int(abs(forecast.edge_after_fees) * Decimal("10000"))
        confidence = max(Decimal("0"), min(Decimal("1"), forecast.confidence_score))
        return TradeProposal(
            id=f"{self.name}_{forecast.market_ticker}_{forecast.timestamp.isoformat()}",
            market_ticker=forecast.market_ticker,
            contract_ticker=forecast.contract_ticker,
            side=side,
            price_cents=price,
            size=1,
            forecast_reference=forecast.proof_reference,
            edge_estimate=EdgeEstimate(
                expected_edge_bps=expected_edge_bps,
                edge_after_fees_bps=edge_after_fees_bps,
                confidence_score=confidence,
            ),
            risk_estimate=("high" if forecast.settlement_risk_score >= Decimal("0.7") else "bounded"),
            confidence_estimate=confidence,
            expected_fill_behavior="passive limit fill within 60s",
            stop_condition="edge evaporates",
            cancellation_condition="stale quote > 30s",
            cap_impact={"single_order_cents": price},
            compliance_verdict=compliance,
            proof_reference=f"strategy_{self.name}_{forecast.proof_reference}",
        )
