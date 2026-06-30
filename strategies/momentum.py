from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class Momentum(StrategyGenome):
    name = "momentum"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        # no-trade: momentum requires time-series velocity data
        return None
