from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class CorrelatedContractArbitrage(StrategyGenome):
    name = "correlated_contract_arbitrage"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        # no-trade: correlated contract data unavailable
        return None
