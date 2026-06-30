from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class StaleQuoteDetection(StrategyGenome):
    name = "stale_quote_detection"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        # no-trade: quotes are fresh in demo
        return None
