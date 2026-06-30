from adapters.base import DumbyAdapter
from core.ontology import Forecast


class KalshiLiveFirewallAdapter(DumbyAdapter):
    """Firewall-side adapter for Kalshi live data.

    This stub intentionally does NOT import or call any Kalshi live order
    endpoints. It only exposes the DumbyAdapter interface so the firewall can
    attach a native forecast to a market data snapshot if one is supplied.
    """

    name = "kalshi_live_firewall"

    def to_native_forecast(self, raw) -> Forecast:
        # The firewall adapter is a pass-through stub; downstream components
        # validate that no live order path is exercised.
        raise NotImplementedError(
            "kalshi_live_firewall adapter is intentionally a stub and does not "
            "transform raw live data into forecasts."
        )
