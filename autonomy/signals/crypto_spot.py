"""Crypto signal: spot + realized volatility vs Kalshi BTC/ETH range markets.

Kalshi crypto markets settle on index prices over short horizons. A driftless
lognormal model over time-to-close, with sigma from recent realized vol
(public Coinbase candles, no key), prices P(settle above strike). Honest
about its own limits: at long horizons or through scheduled events the
uncertainty term widens and the allocator's edge threshold filters it out.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Callable

from autonomy.ontology import MarketView, Signal, Vertical

# e.g. KXBTCD-26JUL0917-T71249.99 — date token with the closing hour glued on.
_TICKER_RE = re.compile(r"^KX(BTC|ETH)[A-Z]*-(\d{2}[A-Z]{3}\d{2})(\d{2})?-[BT]([\d.]+)$")

_PRODUCTS = {"BTC": "BTC-USD", "ETH": "ETH-USD"}


def default_fetch_spot_and_vol(asset: str) -> tuple[float, float]:
    """Return (spot, annualized_vol) from public Coinbase Exchange candles."""
    import httpx

    product = _PRODUCTS[asset]
    candles = httpx.get(
        f"https://api.exchange.coinbase.com/products/{product}/candles",
        params={"granularity": 3600},  # hourly, most recent ~300
        timeout=15,
    )
    candles.raise_for_status()
    rows = candles.json()  # [time, low, high, open, close, volume] newest first
    closes = [float(r[4]) for r in rows[:168]]  # ~7 days hourly
    if len(closes) < 24:
        raise ValueError("insufficient candle history")
    spot = closes[0]
    rets = [math.log(closes[i] / closes[i + 1]) for i in range(len(closes) - 1) if closes[i + 1] > 0]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)
    hourly_sigma = math.sqrt(var)
    annualized = hourly_sigma * math.sqrt(24 * 365)
    return spot, annualized


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def parse_crypto_ticker(ticker: str) -> dict[str, Any] | None:
    match = _TICKER_RE.match(ticker)
    if not match:
        return None
    asset, _date, _hour, strike = match.groups()
    return {"asset": asset, "strike": float(strike)}


class CryptoSpotVolSignal:
    name = "crypto_spot_vol"

    def __init__(self, fetch_spot_and_vol: Callable[[str], tuple[float, float]] | None = None):
        self.fetch_spot_and_vol = fetch_spot_and_vol or default_fetch_spot_and_vol
        self._cache: dict[str, tuple[float, float]] = {}

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.CRYPTO and parse_crypto_ticker(market.ticker) is not None

    def _hours_to_close(self, market: MarketView) -> float:
        try:
            close = datetime.fromisoformat(market.close_time.replace("Z", "+00:00"))
            return max(0.05, (close - datetime.now(timezone.utc)).total_seconds() / 3600.0)
        except Exception:
            return 24.0

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_crypto_ticker(market.ticker)
        if parsed is None:
            return None
        asset = parsed["asset"]
        if asset not in self._cache:
            self._cache[asset] = self.fetch_spot_and_vol(asset)
        spot, annual_vol = self._cache[asset]
        if spot <= 0 or annual_vol <= 0:
            return None
        hours = self._hours_to_close(market)
        horizon_sigma = annual_vol * math.sqrt(hours / (24 * 365))
        if horizon_sigma <= 0:
            return None

        def p_above(strike: float) -> float:
            # Driftless lognormal: P(S_T >= K) = Phi(ln(S/K)/sigma_T)
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
            p_yes = p_above(parsed["strike"])
        p_yes = min(0.995, max(0.005, p_yes))
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=p_yes,
            uncertainty=min(0.5, horizon_sigma),
            rationale=(
                f"{asset} spot={spot:.0f} annvol={annual_vol:.0%} h={hours:.1f} "
                f"{strike_type or 'threshold'} floor={floor} cap={cap}"
            ),
            features={"spot": spot, "annual_vol": annual_vol, "hours_to_close": hours},
        )
