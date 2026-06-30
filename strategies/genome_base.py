from abc import ABC, abstractmethod
from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal


class StrategyGenome(ABC):
    name: str = "base"

    @abstractmethod
    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        ...
