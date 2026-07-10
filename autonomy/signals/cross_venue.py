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


def default_fetch_polymarket_orderbook(token_id: str) -> dict[str, Any]:
    """Read one public CLOB book; no wallet, auth header, or mutation."""
    import httpx

    response = httpx.get(
        "https://clob.polymarket.com/book",
        params={"token_id": token_id},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def default_fetch_polymarket_orderbooks(token_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Batch public CLOB books so a cycle pays one bounded network round trip."""
    import httpx

    if not token_ids:
        return {}
    books: dict[str, dict[str, Any]] = {}
    for offset in range(0, len(token_ids), 500):
        batch = token_ids[offset:offset + 500]
        response = httpx.post(
            "https://clob.polymarket.com/books",
            json=[{"token_id": token_id} for token_id in batch],
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            continue
        for book in payload:
            if not isinstance(book, dict):
                continue
            token_id = str(book.get("asset_id") or "")
            if token_id:
                books[token_id] = book
    return books


def _parse_list(value: Any) -> list[Any] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return None
    return value if isinstance(value, list) else None


def _parse_prices(market: dict[str, Any]) -> list[float] | None:
    raw = _parse_list(market.get("outcomePrices"))
    if raw is None:
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
        token_ids = _parse_list(market.get("clobTokenIds")) or []
        key = (league, frozenset(codes), f"{year}{month}{day}")
        index[key] = {
            "codes": codes,
            "prices": prices,
            "best_bid": market.get("bestBid"),
            "best_ask": market.get("bestAsk"),
            "liquidity": float(market.get("liquidityNum") or market.get("liquidity") or 0) if _is_number(market.get("liquidityNum") or market.get("liquidity")) else 0.0,
            "slug": slug,
            "token_ids": [str(token_id) for token_id in token_ids],
        }
    return index


def _is_number(v: Any) -> bool:
    try:
        float(v)
        return True
    except Exception:
        return False


def _orderbook_quote(book: dict[str, Any]) -> dict[str, float] | None:
    """Normalize a public CLOB snapshot into midpoint, spread, and top depth."""
    bids: list[tuple[float, float]] = []
    asks: list[tuple[float, float]] = []
    for raw, target in ((book.get("bids"), bids), (book.get("asks"), asks)):
        if not isinstance(raw, list):
            continue
        for level in raw:
            if not isinstance(level, dict):
                continue
            try:
                price = float(level.get("price"))
                size = max(0.0, float(level.get("size") or 0))
            except (TypeError, ValueError):
                continue
            if 0.0 < price < 1.0:
                target.append((price, size))
    if not bids or not asks:
        return None
    best_bid = max(price for price, _size in bids)
    best_ask = min(price for price, _size in asks)
    if best_ask < best_bid:
        return None
    return {
        "midpoint": (best_bid + best_ask) / 2.0,
        "spread": best_ask - best_bid,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "best_bid_size": sum(size for price, size in bids if price == best_bid),
        "best_ask_size": sum(size for price, size in asks if price == best_ask),
    }


class CrossVenueSignal:
    name = "cross_venue_polymarket"

    def __init__(
        self,
        fetch_markets: Callable[[], list[dict[str, Any]]] | None = None,
        fetch_orderbook: Callable[[str], dict[str, Any]] | None = None,
        fetch_orderbooks: Callable[[list[str]], dict[str, dict[str, Any]]] | None = None,
    ):
        self.fetch_markets = fetch_markets or default_fetch_polymarket_markets
        self.fetch_orderbook = fetch_orderbook
        self.fetch_orderbooks = (
            fetch_orderbooks
            if fetch_orderbooks is not None
            else (None if fetch_orderbook is not None else default_fetch_polymarket_orderbooks)
        )
        self._index: dict[tuple[str, frozenset[str], str], dict[str, Any]] | None = None
        self._books: dict[str, dict[str, Any] | None] = {}

    def on_cycle_start(self) -> None:
        """Refresh the Polymarket index once per cycle."""
        self._books = {}
        try:
            self._index = index_polymarket(self.fetch_markets())
        except Exception:
            self._index = {}
            return
        if self.fetch_orderbooks is not None:
            token_ids = sorted({
                str(token_id)
                for match in self._index.values()
                for token_id in (match.get("token_ids") or [])
                if token_id
            })
            try:
                self._books.update(self.fetch_orderbooks(token_ids))
            except Exception:
                # Gamma probability remains the explicit fallback.
                pass

    def _ensure_index(self) -> dict[tuple[str, frozenset[str], str], dict[str, Any]]:
        if self._index is None:
            self.on_cycle_start()
        return self._index or {}

    def _book_for(self, token_id: str) -> dict[str, Any] | None:
        if token_id not in self._books:
            if self.fetch_orderbook is None:
                self._books[token_id] = None
                return None
            try:
                payload = self.fetch_orderbook(token_id)
                self._books[token_id] = payload if isinstance(payload, dict) else None
            except Exception:
                self._books[token_id] = None
        return self._books[token_id]

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
        gamma_probability = match["prices"][position]
        p_yes = gamma_probability
        price_source = "gamma_outcome_price"
        token_id = None
        quote = None
        token_ids = match.get("token_ids") or []
        if position < len(token_ids):
            token_id = str(token_ids[position])
            quote = _orderbook_quote(self._book_for(token_id) or {})
            if quote is not None:
                p_yes = quote["midpoint"]
                price_source = "clob_orderbook_midpoint"
        if not (0.0 < p_yes < 1.0):
            return None
        # Uncertainty from Polymarket's own spread + liquidity thinness.
        spread = 0.0
        if quote is not None:
            spread = quote["spread"]
        elif _is_number(match.get("best_ask")) and _is_number(match.get("best_bid")):
            spread = abs(float(match["best_ask"]) - float(match["best_bid"]))
        thinness = 0.0 if match["liquidity"] >= 10_000 else (0.08 if match["liquidity"] >= 1_000 else 0.18)
        top_depth_penalty = 0.0
        if quote is not None:
            two_sided_top_depth = min(quote["best_bid_size"], quote["best_ask_size"])
            top_depth_penalty = 0.03 if two_sided_top_depth < 100 else (
                0.01 if two_sided_top_depth < 500 else 0.0
            )
        uncertainty = min(0.5, max(0.04, spread + thinness + top_depth_penalty))
        features: dict[str, Any] = {
            "polymarket_slug": match["slug"],
            "polymarket_liquidity": match["liquidity"],
            "polymarket_price_source": price_source,
            "polymarket_gamma_probability": gamma_probability,
        }
        if token_id is not None:
            features["polymarket_token_id"] = token_id
        if quote is not None:
            features.update({f"polymarket_{key}": value for key, value in quote.items()})
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=min(0.98, max(0.02, p_yes)),
            uncertainty=uncertainty,
            rationale=(
                f"Polymarket {match['slug']}: {subject}={p_yes:.3f} source={price_source} "
                f"spread={spread:.3f} liq={match['liquidity']:.0f}"
            ),
            features=features,
        )
