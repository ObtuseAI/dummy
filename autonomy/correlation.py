"""Correlation grouping: collapse markets that are really the same bet.

Adjacent BTC strike buckets at one expiry, every temperature bucket for one
city-day, and both sides of one ball game are highly correlated — betting
several is one concentrated position wearing many tickers. `group_key` maps a
ticker to its underlying cluster so the risk brain can cap exposure per
cluster instead of only per ticker.
"""
from __future__ import annotations

import re

_CRYPTO_RE = re.compile(r"^KX(BTC|ETH|SOL|XRP|DOGE)[A-Z]*-(\d{2}[A-Z]{3}\d{2}\d{0,2})")
_COMMODITY_RE = re.compile(r"^KX(WTI|OIL|NATGAS|NGAS|GAS|GOLD)[A-Z]*-(\d{2}[A-Z]{3}\d{2}\d{0,2})")
_WEATHER_RE = re.compile(r"^KX(HIGH|LOW|RAIN|SNOW)([A-Z]+)-(\d{2}[A-Z]{3}\d{2})")
_GAME_RE = re.compile(r"^KX([A-Z]+)GAME-(\d{2}[A-Z]{3}\d{2})(?:\d{2,4})?([A-Z]{4,10})-")

_ASSET_CANON = {"OIL": "WTI", "NGAS": "NATGAS", "GAS": "NATGAS"}


def group_key(ticker: str) -> str:
    """Return the correlated-cluster id for a market ticker."""
    t = ticker.upper()

    m = _CRYPTO_RE.match(t)
    if m:
        return f"CRYPTO:{m.group(1)}:{m.group(2)}"

    m = _COMMODITY_RE.match(t)
    if m:
        asset = _ASSET_CANON.get(m.group(1), m.group(1))
        return f"COMMODITY:{asset}:{m.group(2)}"

    m = _WEATHER_RE.match(t)
    if m:
        return f"WX:{m.group(2)}:{m.group(3)}"

    m = _GAME_RE.match(t)
    if m:
        # Sort the concatenated team codes so both market sides share a key.
        return f"GAME:{m.group(1)}:{m.group(2)}:{''.join(sorted(m.group(3)))}"

    # Fallback: the event stem (everything before the last dash segment).
    parts = t.rsplit("-", 1)
    return f"EVENT:{parts[0]}" if len(parts) == 2 else f"EVENT:{t}"
