from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class NewsLatency(StrategyGenome):
    name = "news_latency"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        # no-trade: news latency requires live news feed
        return None
