from __future__ import annotations

from typing import Optional

from core.ontology import Forecast, OrderBook, TradeProposal
from strategies.genome_base import StrategyGenome


class KalshiWeatherForecastStrategy(StrategyGenome):
    """Retired weather-contract strategy retained for import compatibility.

    Weather observations remain valid contextual inputs for sports research,
    but weather contracts are data-only targets.  Keeping this class as an
    unconditional abstainer prevents old callers or serialized strategy names
    from recovering prediction authority outside the active registry.
    """

    name = "kalshi_weather_forecast"
    DATA_ONLY = True
    PREDICTION_AUTHORITY = False
    RETIREMENT_REASON = "weather contracts are contextual data only"

    def evaluate(self, forecast: Forecast, orderbook: OrderBook) -> Optional[TradeProposal]:
        """Always abstain; weather data has no direct prediction authority."""
        del forecast, orderbook
        return None
