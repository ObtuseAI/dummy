from __future__ import annotations

from typing import Optional

from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class CommoditiesEnergyStrategy(StrategyGenome):
    """Retired commodity-contract strategy retained for import compatibility.

    Commodity observations may remain contextual features for crypto and macro
    research, but commodity contracts are data-only targets.  This class is an
    unconditional abstainer so legacy imports cannot regain proposal authority.
    """

    name = "commodities_energy"
    DATA_ONLY = True
    PREDICTION_AUTHORITY = False
    RETIREMENT_REASON = "commodity contracts are contextual data only"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        """Always abstain; commodity data has no direct prediction authority."""
        del forecast, orderbook
        return None
