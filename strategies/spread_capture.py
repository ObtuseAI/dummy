from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class SpreadCapture(StrategyGenome):
    name = "spread_capture"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        # no-trade: spread capture requires tighter spreads than demo book
        return None
