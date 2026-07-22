from __future__ import annotations

from typing import Optional

from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class StockMacroMomentumStrategy(StrategyGenome):
    """Quarantined legacy stock/index/macro strategy.

    The historical implementation had no reliable target applicability check.
    It could therefore emit a stock-labelled proposal for an unrelated weather
    or sports forecast.  Keep the class for artifact/import compatibility, but
    permanently deny it prediction authority.
    """

    name = "stock_macro_momentum"
    PREDICTION_AUTHORITY = False
    INTEGRATION_STATUS = "excluded_unsupported_prediction_target"
    QUARANTINE_REASON = "outside_supported_prediction_targets"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        del forecast, orderbook
        return None
