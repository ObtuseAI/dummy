"""Cross-venue signal: Polymarket implied probability as an independent voice.

Polymarket and Kalshi both list single-game sports moneylines. Polymarket's
crypto-native liquidity often prices these differently; that disagreement is
alpha the calibration ledger can grade. Matching is fail-closed — a signal is
emitted only on an exact team-set + date match on the same league, so a wrong
match can never inject a phantom edge. Public Gamma API, read-only.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.sports_elo import parse_game_ticker

_SLUG_RE = re.compile(r"^(mlb|nba|nfl|nhl|wnba)-([a-z]{2,4})-([a-z]{2,4})-(\d{4})-(\d{2})-(\d{2})$")

# Polymarket slug abbreviations that differ from ESPN/Kalshi codes.
_CODE_ALIASES: dict[str, str] = {
    "WSH": "WAS", "NOP": "NO", "GSW": "GS", "SAS": "SA", "NYK": "NY",
}


def _norm(code: str) -> str:
    up = code.upper()
    return _CODE_ALIASES.get(up, up)


def default_fetch_polymarket_markets(max_pages: int = 6, page_size: int = 100) -> list[dict[str, Any]]:
    """Paginate the Gamma markets feed (it caps ~100/page) by descending volume."""
    import httpx

    collected: list[dict[str, Any]] = []
    for page in range(max_pages):
        response = httpx.get(
            "https://gamma-api.polymarket.com/markets",
            params={
                "closed": "false", "active": "true", "limit": page_size,
                "offset": page * page_size, "order": "volume", "ascending": "false",
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        batch = data if isinstance(data, list) else data.get("data", [])
        if not batch:
            break
        collected.extend(batch)
        if len(batch) < page_size:
            break
    return collected


def _parse_prices(market: dict[str, Any]) -> list[float] | None:
    raw = market.get("outcomePrices")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None
    if not isinstance(raw, list):
        return None
    try:
        return [float(p) for p in raw]
    except Exception:
        return None


def index_polymarket(markets: list[dict[str, Any]]) -> dict[tuple[str, frozenset[str], str], dict[str, Any]]:
    """Key sports markets by (league, {codeA,codeB}, YYYYMMDD)."""
    index: dict[tuple[str, frozenset[str], str], dict[str, Any]] = {}
    for market in markets:
        slug = str(market.get("slug", ""))
        match = _SLUG_RE.match(slug)
        if not match:
            continue
        league, code_a, code_b, year, month, day = match.groups()
        prices = _parse_prices(market)
        if not prices or len(prices) != 2:
            continue
        codes = [_norm(code_a), _norm(code_b)]
        key = (league, frozenset(codes), f"{year}{month}{day}")
        index[key] = {
            "codes": codes,
            "prices": prices,
            "best_bid": market.get("bestBid"),
            "best_ask": market.get("bestAsk"),
            "liquidity": float(market.get("liquidityNum") or market.get("liquidity") or 0) if _is_number(market.get("liquidityNum") or market.get("liquidity")) else 0.0,
            "slug": slug,
        }
    return index


def _is_number(v: Any) -> bool:
    try:
        float(v)
        return True
    except Exception:
        return False


class CrossVenueSignal:
    name = "cross_venue_polymarket"

    def __init__(self, fetch_markets: Callable[[], list[dict[str, Any]]] | None = None):
        self.fetch_markets = fetch_markets or default_fetch_polymarket_markets
        self._index: dict[tuple[str, frozenset[str], str], dict[str, Any]] | None = None

    def on_cycle_start(self) -> None:
        """Refresh the Polymarket index once per cycle."""
        try:
            self._index = index_polymarket(self.fetch_markets())
        except Exception:
            self._index = {}

    def _ensure_index(self) -> dict[tuple[str, frozenset[str], str], dict[str, Any]]:
        if self._index is None:
            self.on_cycle_start()
        return self._index or {}

    def applicable(self, market: MarketView) -> bool:
        return market.vertical is Vertical.SPORTS and parse_game_ticker(market.ticker) is not None

    def generate(self, market: MarketView) -> Signal | None:
        parsed = parse_game_ticker(market.ticker)
        if parsed is None:
            return None
        subject, opponent = _norm(parsed["subject"]), _norm(parsed["opponent"])
        key = (parsed["league"], frozenset({subject, opponent}), parsed["date_yyyymmdd"])
        match = self._ensure_index().get(key)
        if match is None:
            return None  # fail-closed: no confident cross-venue match
        try:
            position = match["codes"].index(subject)
        except ValueError:
            return None
        p_yes = match["prices"][position]
        if not (0.0 < p_yes < 1.0):
            return None
        # Uncertainty from Polymarket's own spread + liquidity thinness.
        spread = 0.0
        if _is_number(match.get("best_ask")) and _is_number(match.get("best_bid")):
            spread = abs(float(match["best_ask"]) - float(match["best_bid"]))
        thinness = 0.0 if match["liquidity"] >= 10_000 else (0.08 if match["liquidity"] >= 1_000 else 0.18)
        uncertainty = min(0.5, max(0.04, spread + thinness))
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=min(0.98, max(0.02, p_yes)),
            uncertainty=uncertainty,
            rationale=(
                f"Polymarket {match['slug']}: {subject}={p_yes:.3f} "
                f"spread={spread:.3f} liq={match['liquidity']:.0f}"
            ),
            features={"polymarket_slug": match["slug"], "polymarket_liquidity": match["liquidity"]},
        )
