from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class ImpliedProbabilityReversion(StrategyGenome):
    name = "implied_probability_reversion"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        # no-trade: reversion signal not triggered
        return None
