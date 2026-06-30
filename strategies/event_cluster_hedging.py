from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class EventClusterHedging(StrategyGenome):
    name = "event_cluster_hedging"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        # no-trade: no correlated event cluster configured
        return None
