from datetime import datetime, timedelta, timezone
from decimal import Decimal
from core.ontology import Forecast, OrderBook


class ForecastEngine:
    def forecast(
        self,
        market_ticker: str,
        contract_ticker: str,
        event_title: str,
        contract_title: str,
        orderbook: OrderBook,
    ) -> Forecast:
        if orderbook.bids and orderbook.asks:
            mid = Decimal((orderbook.bids[0].price + orderbook.asks[0].price) / 200)
        else:
            mid = Decimal("0.5")
        dummy_prob = (mid + Decimal("0.03")).quantize(Decimal("0.0001"))
        edge = (dummy_prob - mid).quantize(Decimal("0.0001"))
        return Forecast(
            market_ticker=market_ticker,
            contract_ticker=contract_ticker,
            event_title=event_title,
            contract_title=contract_title,
            market_implied_probability=mid,
            dummy_probability=dummy_prob,
            probability_delta=edge,
            confidence_score=Decimal("0.6"),
            uncertainty_band=(
                max(Decimal("0"), dummy_prob - Decimal("0.05")),
                min(Decimal("1"), dummy_prob + Decimal("0.05")),
            ),
            expected_edge=edge,
            edge_after_fees=(edge - Decimal("0.005")).quantize(Decimal("0.0001")),
            freshness_score=Decimal("1.0"),
            liquidity_score=Decimal("0.7"),
            spread_score=Decimal("0.8"),
            orderbook_depth_score=Decimal("0.6"),
            settlement_risk_score=Decimal("0.2"),
            source_summary="orderbook_disagreement",
            model_summary="naive_mid_plus_edge",
            calibration_notes="demo model",
            timestamp=datetime.now(timezone.utc),
            expiration=datetime.now(timezone.utc) + timedelta(hours=1),
            strategy_references=["probability_disagreement"],
            proof_reference=f"forecast_{market_ticker}_{datetime.now(timezone.utc).isoformat()}",
        )
