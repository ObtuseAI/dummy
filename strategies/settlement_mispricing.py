from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class SettlementMispricing(StrategyGenome):
    name = "settlement_mispricing"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        # no-trade: settlement mispricing requires settlement event stream
        return None
