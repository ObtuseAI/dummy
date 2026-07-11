"""Market scanner: sweep live Kalshi markets, classify verticals, shortlist.

Public GET endpoints only. The scanner is the predator's eyes — it never
mutates anything and never authenticates.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from autonomy.ontology import MarketView, Vertical

_VERTICAL_PREFIXES: list[tuple[str, Vertical]] = [
    ("KXHIGH", Vertical.WEATHER),
    ("KXLOW", Vertical.WEATHER),
    ("KXRAIN", Vertical.WEATHER),
    ("KXSNOW", Vertical.WEATHER),
    ("KXBTC", Vertical.CRYPTO),
    ("KXETH", Vertical.CRYPTO),
    ("KXSOL", Vertical.CRYPTO),
    ("BTCD", Vertical.CRYPTO),
    ("BTC", Vertical.CRYPTO),
    ("ETHD", Vertical.CRYPTO),
    ("ETH", Vertical.CRYPTO),
    ("KXNBA", Vertical.SPORTS),
    ("KXNFL", Vertical.SPORTS),
    ("KXMLB", Vertical.SPORTS),
    ("KXNHL", Vertical.SPORTS),
    ("KXUFC", Vertical.SPORTS),
    ("KXF1", Vertical.SPORTS),
    ("KXWTA", Vertical.SPORTS),
    ("KXATP", Vertical.SPORTS),
    ("KXMVESPORTS", Vertical.SPORTS),
    ("KXESPORTS", Vertical.SPORTS),
    ("KXOIL", Vertical.COMMODITIES),
    ("KXWTI", Vertical.COMMODITIES),
    ("KXNATGAS", Vertical.COMMODITIES),
    ("KXNGAS", Vertical.COMMODITIES),
    ("KXGAS", Vertical.COMMODITIES),
    ("KXGOLD", Vertical.COMMODITIES),
    ("KXCPI", Vertical.ECON),
    ("KXFED", Vertical.ECON),
    ("KXGDP", Vertical.ECON),
    ("KXPAYROLL", Vertical.ECON),
]


def classify_vertical(ticker: str) -> Vertical:
    upper = ticker.upper()
    for prefix, vertical in _VERTICAL_PREFIXES:
        if upper.startswith(prefix):
            return vertical
    return Vertical.OTHER


# Curated hunting grounds: series with real exogenous signal coverage. A raw
# paginated sweep of /markets drowns in thousands of auto-generated MVE parlay
# combos; series-targeted queries go straight to where the edge sources live.
WATCHLIST_SERIES: list[str] = [
    # Weather prediction retired 2026-07-11 (net loser vs the sharp Kalshi
    # weather market). The Open-Meteo pipeline now feeds MLB as a feature
    # (autonomy/sports/ballpark_weather.py), not a trading target, so the
    # daemon no longer fetches KXHIGH* weather series here.
    # Exact crypto universe: BTC/ETH/SOL at native 15m plus mixed-cadence
    # direct-price series. Event duration separates hourly/daily/weekly rows.
    "KXBTC15M", "KXETH15M", "KXSOL15M",
    "KXBTCD", "KXBTC", "KXETHD", "KXETH", "KXSOLD", "KXSOLE",
    "BTCD", "BTC", "ETHD", "ETH",
    # Sports intelligence: active moneylines plus settlement-trained MLB runs
    # and UFC fight-duration challengers. All external reads are public GETs.
    "KXMLBGAME", "KXNBAGAME", "KXNFLGAME", "KXNCAAFGAME", "KXNHLGAME",
    "KXNCAAMBGAME", "KXWNBAGAME",
    "KXMLBTOTAL", "KXMLBRFI",
    "KXNBATOTAL", "KXNFLTOTAL", "KXNCAAFTOTAL", "KXNHLTOTAL", "KXNCAAMBTOTAL",
    "KXUFCFIGHT", "KXUFCROUNDS", "KXUFCDISTANCE",
    "KXF1RACE",
    # Daily/weekly commodity price thresholds (Yahoo proxy + realized vol).
    "KXWTI", "KXNATGASD", "KXGOLDD",
    "KXWTIW", "KXNATGASW", "KXGOLDW",
]


def _public_base() -> str:
    base = os.environ.get("KALSHI_API_BASE", "https://api.elections.kalshi.com").rstrip("/")
    version = os.environ.get("KALSHI_API_VERSION", "trade-api/v2").strip("/")
    return f"{base}/{version}"


def default_fetch_series_markets(series_ticker: str) -> dict[str, Any]:
    import httpx

    response = httpx.get(
        f"{_public_base()}/markets",
        params={"series_ticker": series_ticker, "status": "open", "limit": 1000},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _dollars_to_cents(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value) * 100))
    except Exception:
        return None


def _price_field(raw: dict[str, Any], cent_key: str) -> int | None:
    """Prefer integer-cent fields; fall back to the *_dollars string schema."""
    if raw.get(cent_key) is not None:
        try:
            return int(raw[cent_key])
        except Exception:
            pass
    return _dollars_to_cents(raw.get(f"{cent_key}_dollars"))


def _normalize_binary_quotes(raw: dict[str, Any]) -> tuple[
    int | None, int | None, int | None, int | None,
]:
    """Treat 0/100 book sentinels as absent and restore complements."""
    yes_bid = _price_field(raw, "yes_bid")
    yes_ask = _price_field(raw, "yes_ask")
    no_bid = _price_field(raw, "no_bid")
    no_ask = _price_field(raw, "no_ask")
    yes_bid = yes_bid if yes_bid is not None and 0 < yes_bid < 100 else None
    yes_ask = yes_ask if yes_ask is not None and 0 < yes_ask < 100 else None
    no_bid = no_bid if no_bid is not None and 0 < no_bid < 100 else None
    no_ask = no_ask if no_ask is not None and 0 < no_ask < 100 else None
    if yes_ask is None and no_bid is not None:
        yes_ask = 100 - no_bid
    if no_bid is None and yes_ask is not None:
        no_bid = 100 - yes_ask
    if yes_bid is None and no_ask is not None:
        yes_bid = 100 - no_ask
    if no_ask is None and yes_bid is not None:
        no_ask = 100 - yes_bid
    return yes_bid, yes_ask, no_bid, no_ask


def to_market_view(raw: dict[str, Any]) -> MarketView:
    ticker = str(raw.get("ticker", ""))
    volume = raw.get("volume")
    if volume is None:
        try:
            volume = float(raw.get("volume_fp") or raw.get("volume_24h_fp") or 0)
        except Exception:
            volume = 0
    liquidity = raw.get("liquidity")
    if liquidity is None:
        liquidity = _dollars_to_cents(raw.get("liquidity_dollars")) or 0
    yes_bid, yes_ask, no_bid, no_ask = _normalize_binary_quotes(raw)
    return MarketView(
        ticker=ticker,
        title=str(raw.get("title", "")),
        vertical=classify_vertical(ticker),
        status=str(raw.get("status", "")),
        close_time=str(raw.get("close_time", "")),
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=no_bid,
        no_ask=no_ask,
        volume=int(volume or 0),
        liquidity=int(liquidity or 0),
        tick_size=int(raw.get("tick_size") or 1),
        raw=raw,
    )


class MarketScanner:
    def __init__(
        self,
        fetch_series: Callable[[str], dict[str, Any]] | None = None,
        watchlist: list[str] | None = None,
        verticals: set[Vertical] | None = None,
    ) -> None:
        self.fetch_series = fetch_series or default_fetch_series_markets
        self.watchlist = watchlist or list(WATCHLIST_SERIES)
        self.verticals = verticals or {Vertical.CRYPTO, Vertical.SPORTS,
                                       Vertical.COMMODITIES, Vertical.ECON}

    def scan(self) -> list[MarketView]:
        views: list[MarketView] = []
        seen: set[str] = set()
        for series in self.watchlist:
            try:
                page = self.fetch_series(series)
            except Exception:
                continue  # one dead series never stalls the hunt
            for raw in page.get("markets", []):
                view = to_market_view(raw)
                if view.ticker in seen or view.status not in ("active", "open"):
                    continue
                if view.vertical not in self.verticals:
                    continue
                seen.add(view.ticker)
                views.append(view)
        return views
