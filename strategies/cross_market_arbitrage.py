from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class CrossMarketArbitrage(StrategyGenome):
    name = "cross_market_arbitrage"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        # no-trade: cross-market arbitrage requires second venue data
        return None
