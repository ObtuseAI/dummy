"""Commodity market-data helpers retained for contextual macro features.

Kalshi lists WTI crude (KXWTI), and periodically natural gas and gold, as
Direct commodity-contract probabilities were retired. The Yahoo helpers remain
available as data plumbing, while the compatibility signal class is permanently
non-applicable and emits no forecast.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Callable

from autonomy.ontology import MarketView, Signal

# Kalshi series prefix -> Yahoo Finance continuous-future symbol.
_ASSET_SYMBOL: list[tuple[str, str]] = [
    ("KXWTI", "CL=F"),
    ("KXOIL", "CL=F"),
    ("KXNATGAS", "NG=F"),
    ("KXNGAS", "NG=F"),
    ("KXGAS", "NG=F"),
    ("KXGOLD", "GC=F"),
]

_TICKER_RE = re.compile(r"^KX[A-Z]+-(\d{2}[A-Z]{3}\d{2})(\d{2})?-[BT]([\d.]+)$")


def _symbol_for(ticker: str) -> str | None:
    upper = ticker.upper()
    for prefix, symbol in _ASSET_SYMBOL:
        if upper.startswith(prefix):
            return symbol
    return None


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def default_fetch_spot_and_vol(symbol: str) -> tuple[float, float]:
    """(spot, annualized_vol) from keyless Yahoo Finance daily candles."""
    import httpx

    response = httpx.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        params={"range": "3mo", "interval": "1d"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    result = response.json()["chart"]["result"][0]
    closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]
    if len(closes) < 20:
        raise ValueError("insufficient candle history")
    spot = float(result["meta"].get("regularMarketPrice") or closes[-1])
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))
            if closes[i - 1] > 0 and closes[i] > 0]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)
    annualized = math.sqrt(var) * math.sqrt(252)  # trading days
    return spot, annualized


class CommoditiesSpotVolSignal:
    """Retired compatibility shell; commodity prices are context data only."""

    name = "commodities_spot_vol"
    data_only = True
    prediction_authority = False

    def __init__(self, fetch_spot_and_vol: Callable[[str], tuple[float, float]] | None = None):
        self.fetch_spot_and_vol = fetch_spot_and_vol or default_fetch_spot_and_vol
        self._cache: dict[str, tuple[float, float]] = {}

    def on_cycle_start(self) -> None:
        self._cache.clear()

    def applicable(self, market: MarketView) -> bool:
        return False

    def _hours_to_close(self, market: MarketView) -> float:
        try:
            close = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
            return max(0.5, (close - datetime.now(timezone.utc)).total_seconds() / 3600.0)
        except Exception:
            return 24.0

    def generate(self, market: MarketView) -> Signal | None:
        return None
