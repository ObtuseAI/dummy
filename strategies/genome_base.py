from abc import ABC, abstractmethod
from typing import Optional
from core.ontology import Forecast, OrderBook, TradeProposal


class StrategyGenome(ABC):
    name: str = "base"
    DATA_ONLY: bool = False
    PREDICTION_AUTHORITY: bool = True
    EXECUTION_AUTHORITY: bool = False

    @abstractmethod
    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        ...
