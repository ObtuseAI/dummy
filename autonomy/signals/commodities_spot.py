"""Commodities signal: spot + realized vol vs Kalshi price-threshold markets.

Kalshi lists WTI crude (KXWTI), and periodically natural gas and gold, as
price-threshold markets that settle on the underlying. A driftless lognormal
over time-to-close — with sigma from recent daily realized vol (keyless Yahoo
Finance chart API) — prices P(settle above/below/between strikes), exactly the
crypto approach adapted to slower-moving commodity vol. Fail-closed: no feed,
no signal.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Callable

from autonomy.ontology import MarketView, Signal, Vertical

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
    name = "commodities_spot_vol"

    def __init__(self, fetch_spot_and_vol: Callable[[str], tuple[float, float]] | None = None):
        self.fetch_spot_and_vol = fetch_spot_and_vol or default_fetch_spot_and_vol
        self._cache: dict[str, tuple[float, float]] = {}

    def on_cycle_start(self) -> None:
        self._cache.clear()

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.COMMODITIES and _symbol_for(market.ticker) is not None

    def _hours_to_close(self, market: MarketView) -> float:
        try:
            close = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
            return max(0.5, (close - datetime.now(timezone.utc)).total_seconds() / 3600.0)
        except Exception:
            return 24.0

    def generate(self, market: MarketView) -> Signal | None:
        symbol = _symbol_for(market.ticker)
        if symbol is None:
            return None
        if symbol not in self._cache:
            try:
                self._cache[symbol] = self.fetch_spot_and_vol(symbol)
            except Exception:
                return None
        spot, annual_vol = self._cache[symbol]
        if spot <= 0 or annual_vol <= 0:
            return None
        hours = self._hours_to_close(market)
        horizon_sigma = annual_vol * math.sqrt(hours / (24 * 365))
        if horizon_sigma <= 0:
            return None

        def p_above(strike: float) -> float:
            if strike <= 0:
                return 1.0
            return _normal_cdf(math.log(spot / strike) / horizon_sigma)

        strike_type = str(market.raw.get("strike_type", "")).lower()
        floor = market.raw.get("floor_strike")
        cap = market.raw.get("cap_strike")
        if strike_type == "greater" and floor is not None:
            p_yes = p_above(float(floor))
        elif strike_type == "less" and cap is not None:
            p_yes = 1.0 - p_above(float(cap))
        elif strike_type == "between" and floor is not None and cap is not None:
            p_yes = p_above(float(floor)) - p_above(float(cap))
        else:
            match = _TICKER_RE.match(market.ticker)
            if not match:
                return None
            p_yes = p_above(float(match.group(3)))
        p_yes = min(0.98, max(0.02, p_yes))
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=min(0.5, horizon_sigma),
            rationale=(
                f"{symbol} spot={spot:.2f} annvol={annual_vol:.0%} h={hours:.1f} "
                f"{strike_type or 'threshold'} floor={floor} cap={cap}"
            ),
            features={"symbol": symbol, "spot": spot, "annual_vol": annual_vol, "hours_to_close": hours},
        )
