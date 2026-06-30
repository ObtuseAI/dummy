from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class LiquidityDislocation(StrategyGenome):
    name = "liquidity_dislocation"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        # no-trade: no cross-book liquidity dislocation detected
        return None
