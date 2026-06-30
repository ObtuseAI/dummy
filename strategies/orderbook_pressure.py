from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class OrderbookPressure(StrategyGenome):
    name = "orderbook_pressure"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        # no-trade: orderbook pressure imbalance not present
        return None
