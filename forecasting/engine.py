from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from core.ontology import Forecast, OrderBook


def kalshi_fee_cents(probability: Decimal, contracts: int = 1) -> int:
    """Return Kalshi's rounded-up taker fee estimate in cents."""
    p = max(Decimal("0"), min(Decimal("1"), Decimal(probability)))
    raw = Decimal("0.07") * Decimal(contracts) * Decimal("100") * p * (Decimal("1") - p)
    return int(raw.to_integral_value(rounding=ROUND_CEILING))


def signed_edge_after_fees(edge: Decimal, fee_probability: Decimal) -> Decimal:
    """Deduct fees without allowing costs to manufacture an opposite edge."""
    magnitude = max(Decimal("0"), abs(edge) - max(Decimal("0"), fee_probability))
    if edge < 0:
        return -magnitude
    return magnitude


class ForecastEngine:
    def forecast(
        self,
        market_ticker: str,
        contract_ticker: str,
        event_title: str,
        contract_title: str,
        orderbook: OrderBook,
    ) -> Forecast | None:
        if not orderbook.bids or not orderbook.asks:
            return None
        # Canonical books sort bids ascending and asks ascending. The best bid
        # is therefore the last bid; avoid binary-float conversion.
        best_bid = orderbook.bids[-1]
        best_ask = orderbook.asks[0]
        if best_bid.price >= best_ask.price:
            return None
        mid = (Decimal(best_bid.price) + Decimal(best_ask.price)) / Decimal(200)
        spread_cents = best_ask.price - best_bid.price
        bid_size = Decimal(best_bid.size)
        ask_size = Decimal(best_ask.size)
        top_size = bid_size + ask_size
        imbalance = (bid_size - ask_size) / top_size if top_size else Decimal("0")
        spread_score = max(Decimal("0"), Decimal("1") - Decimal(spread_cents) / Decimal("20"))
        depth_score = min(Decimal("1"), top_size / Decimal("1000"))
        liquidity_score = (spread_score * depth_score).quantize(Decimal("0.0001"))
        adjustment = (imbalance * Decimal("0.05") * liquidity_score).quantize(Decimal("0.0001"))
        dummy_prob = max(Decimal("0"), min(Decimal("1"), mid + adjustment)).quantize(Decimal("0.0001"))
        edge = (dummy_prob - mid).quantize(Decimal("0.0001"))
        source_ts = orderbook.source_ts or orderbook.timestamp
        age_seconds = max(0.0, (datetime.now(timezone.utc) - source_ts).total_seconds())
        freshness = Decimal(str(round(max(0.0, 1.0 - age_seconds / 300.0), 4)))
        confidence = (liquidity_score * freshness).quantize(Decimal("0.0001"))
        band_width = max(Decimal("0.03"), (Decimal("1") - confidence) * Decimal("0.20"))
        fee_probability = Decimal(kalshi_fee_cents(mid)) / Decimal("100")
        edge_after_fees = signed_edge_after_fees(edge, fee_probability)
        now = datetime.now(timezone.utc)
        return Forecast(
            market_ticker=market_ticker,
            contract_ticker=contract_ticker,
            event_title=event_title,
            contract_title=contract_title,
            market_implied_probability=mid,
            dummy_probability=dummy_prob,
            probability_delta=edge,
            confidence_score=confidence,
            uncertainty_band=(
                max(Decimal("0"), dummy_prob - band_width),
                min(Decimal("1"), dummy_prob + band_width),
            ),
            expected_edge=edge,
            edge_after_fees=edge_after_fees.quantize(Decimal("0.0001")),
            freshness_score=freshness,
            liquidity_score=liquidity_score,
            spread_score=spread_score.quantize(Decimal("0.0001")),
            orderbook_depth_score=depth_score.quantize(Decimal("0.0001")),
            settlement_risk_score=Decimal("0.30"),
            source_summary="orderbook_top_level_imbalance",
            model_summary="deterministic_orderbook_baseline",
            calibration_notes="No exogenous signal; symmetric books produce zero edge",
            timestamp=now,
            expiration=now + timedelta(hours=1),
            strategy_references=["probability_disagreement"],
            proof_reference=f"forecast_{market_ticker}_{now.isoformat()}",
        )
