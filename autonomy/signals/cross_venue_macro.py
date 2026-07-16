"""Cross-venue Polymarket reference pricing for CRYPTO and ECON Kalshi markets.

Wave-2 E4. Extends the sports cross-venue idea (autonomy/signals/cross_venue.py)
to Kalshi crypto strike ladders and econ (Fed decision / Core-CPI) markets: a
free, independent second-sharp price from Polymarket, matched fail-closed.

Two challenger signals, each on its OWN source name / taxonomy scope / session
registration -- they do NOT inherit the sports scope's earned champion status:

  * ``cross_venue_polymarket_crypto`` -- Kalshi KXBTC*/KXETH*/KXSOL* threshold
    ladders (above / below / between a strike on a date) matched to Polymarket
    "Will the price of X be {above|less than|between} $K on <date>".
  * ``cross_venue_polymarket_econ`` -- Kalshi KXFED* (Fed rate decision) and
    KXCPI (Core CPI YoY) matched to the equivalent Polymarket outcome markets.

Every emission is stamped ``challenger_only=True`` and deliberately does NOT
stamp ``promotion_eligible``: promotion is evidence-driven -- the base's
AutoPromotionEngine (docs/AUTO_PROMOTION.md) earns each exact scope its place
from settled proof-of-profit, and inheriting the sports champion's status would
be unearned. Matching is exact: any asset / strike / date / outcome mismatch or
ambiguity yields NO match and the source abstains, so a wrong cross-venue map
can never inject a phantom edge. Public Gamma + CLOB endpoints, read-only; no
Polymarket execution, ever.

Coverage is intentionally partial (many Kalshi strikes have no Polymarket
equivalent). The per-cycle match rate is exposed in ``diagnostics()`` and every
matched market's Kalshi-vs-Polymarket divergence is persisted through
``record_external_observation`` (source ``polymarket_crypto`` / ``polymarket_econ``)
so later CLV / disagreement-backtest campaigns have a point-in-time record.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable

from autonomy.ontology import MarketView, Signal, Vertical
from autonomy.signals.cross_venue import (
    _is_number,
    _orderbook_quote,
    _parse_list,
    _parse_prices,
    default_fetch_polymarket_markets,
    default_fetch_polymarket_orderbooks,
)
from autonomy.signals.crypto_spot import parse_crypto_ticker

# ---------------------------------------------------------------------------
# Shared parse helpers
# ---------------------------------------------------------------------------

_CRYPTO_ASSET = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}

# "Will the price of Bitcoin be above $62,000 on July 20?"
# "... be less than $1,300 on July 17?"  /  "... be between $1,600 and $1,700 ..."
_CRYPTO_Q_RE = re.compile(
    r"price of (bitcoin|ethereum|solana) be "
    r"(above|below|less than|greater than|between)\s+"
    r"\$?([\d,]+(?:\.\d+)?)(?:\s+and\s+\$?([\d,]+(?:\.\d+)?))?\s+on",
    re.IGNORECASE,
)

# "Will the Fed decrease interest rates by 25 bps after the September 2026 meeting?"
# "... decrease interest rates by 50+ bps after the July 2026 meeting?"
_FED_Q_RE = re.compile(
    r"fed (decrease|increase|cut|hike|raise|lower|lowers|raises|cuts|hikes)"
    r"\s+interest rates by\s+(\d+)\+?\s*bps",
    re.IGNORECASE,
)
_FED_NOCHANGE_RE = re.compile(
    r"fed (not change|hold|keep|leave|make no change|pause)"
    r"|no change (in|to) (interest )?rates",
    re.IGNORECASE,
)

# "Will Core CPI YoY be 2.5% in July?"  /  "... be 2.2% or less in July?"
_CPI_Q_RE = re.compile(
    r"(?:core )?cpi (?:yoy|year[- ]over[- ]year|y/y)\s+be\s+"
    r"(\d+(?:\.\d+)?)%\s*(or less|or more|or higher|or lower)?",
    re.IGNORECASE,
)

_FED_DIR = {
    "decrease": "decrease", "cut": "decrease", "cuts": "decrease",
    "lower": "decrease", "lowers": "decrease",
    "increase": "increase", "hike": "increase", "hikes": "increase",
    "raise": "increase", "raises": "increase",
}


def _strike_key(value: float) -> str:
    """Canonical, formatting-stable key for one strike level."""
    return f"{float(value):.2f}"


def _value_key(value: float) -> str:
    """Canonical key for a percentage-point econ value (0.1pp resolution)."""
    return f"{round(float(value), 1):.1f}"


def _clean_number(raw: str) -> float | None:
    try:
        return float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _utc_date_yyyymmdd(iso: str) -> str | None:
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%d")


def _utc_yyyymm(iso: str) -> str | None:
    day = _utc_date_yyyymmdd(iso)
    return day[:6] if day else None


# ---------------------------------------------------------------------------
# Polymarket discovery indices
# ---------------------------------------------------------------------------

# key: (asset, comparator, strike_key_or_pair, YYYYMMDD)
CryptoKey = tuple[str, str, str, str]
# key: (YYYYMM, outcome_label)
EconKey = tuple[str, str]


def _index_common(market: dict[str, Any]) -> dict[str, Any] | None:
    """Shared per-market fields (prices, book tokens, liquidity, spread)."""
    prices = _parse_prices(market)
    if not prices or len(prices) != 2:
        return None
    token_ids = [str(t) for t in (_parse_list(market.get("clobTokenIds")) or [])]
    liq_raw = market.get("liquidityNum")
    if liq_raw is None:
        liq_raw = market.get("liquidity")
    liquidity = float(liq_raw) if _is_number(liq_raw) else 0.0
    return {
        "prices": prices,
        "best_bid": market.get("bestBid"),
        "best_ask": market.get("bestAsk"),
        "liquidity": liquidity,
        "slug": str(market.get("slug", "")),
        "token_ids": token_ids,
    }


def index_polymarket_crypto(markets: list[dict[str, Any]]) -> dict[CryptoKey, dict[str, Any]]:
    """Key crypto threshold markets by (asset, comparator, strike, YYYYMMDD)."""
    index: dict[CryptoKey, dict[str, Any]] = {}
    for market in markets:
        parsed = parse_crypto_pm_question(str(market.get("question", "")))
        if parsed is None:
            continue
        date = _utc_date_yyyymmdd(str(market.get("endDate", "")))
        if date is None:
            continue
        common = _index_common(market)
        if common is None:
            continue
        key: CryptoKey = (parsed["asset"], parsed["comparator"], parsed["strike_key"], date)
        # First (highest-volume) listing wins; discovery is volume-descending.
        index.setdefault(key, {**common, **parsed, "date": date})
    return index


def index_polymarket_econ(markets: list[dict[str, Any]]) -> dict[EconKey, dict[str, Any]]:
    """Key Fed / CPI markets by (YYYYMM, canonical-outcome-label)."""
    index: dict[EconKey, dict[str, Any]] = {}
    for market in markets:
        question = str(market.get("question", ""))
        parsed = parse_fed_pm_question(question) or parse_cpi_pm_question(question)
        if parsed is None:
            continue
        month = _utc_yyyymm(str(market.get("endDate", "")))
        if month is None:
            continue
        common = _index_common(market)
        if common is None:
            continue
        key: EconKey = (month, parsed["outcome"])
        index.setdefault(key, {**common, **parsed, "month": month})
    return index


def parse_crypto_pm_question(question: str) -> dict[str, Any] | None:
    """Parse a Polymarket crypto threshold question into an exact match key."""
    match = _CRYPTO_Q_RE.search(question or "")
    if match is None:
        return None
    asset_word, comp_word, first, second = match.groups()
    asset = _CRYPTO_ASSET.get(asset_word.lower())
    if asset is None:
        return None
    comp_word = comp_word.lower()
    lo = _clean_number(first)
    if lo is None:
        return None
    if comp_word == "between":
        hi = _clean_number(second)
        if hi is None:
            return None
        low, high = sorted((lo, hi))
        return {
            "asset": asset, "comparator": "between",
            "strike_key": f"{_strike_key(low)}|{_strike_key(high)}",
            "strike_low": low, "strike_high": high,
        }
    comparator = "above" if comp_word in {"above", "greater than"} else "below"
    return {
        "asset": asset, "comparator": comparator,
        "strike_key": _strike_key(lo), "strike": lo,
    }


def parse_fed_pm_question(question: str) -> dict[str, Any] | None:
    """Parse a Polymarket Fed-decision question into a canonical outcome label."""
    text = question or ""
    match = _FED_Q_RE.search(text)
    if match is not None:
        direction = _FED_DIR.get(match.group(1).lower())
        if direction is None:
            return None
        try:
            bps = int(match.group(2))
        except (TypeError, ValueError):
            return None
        return {"kind": "fed", "outcome": f"fed:{direction}:{bps}",
                "fed_direction": direction, "fed_bps": bps}
    if _FED_NOCHANGE_RE.search(text):
        return {"kind": "fed", "outcome": "fed:no_change:0",
                "fed_direction": "no_change", "fed_bps": 0}
    return None


def parse_cpi_pm_question(question: str) -> dict[str, Any] | None:
    """Parse a Polymarket Core-CPI question into a canonical outcome label."""
    match = _CPI_Q_RE.search(question or "")
    if match is None:
        return None
    value = _clean_number(match.group(1))
    if value is None:
        return None
    modifier = (match.group(2) or "").lower()
    if modifier in {"or less", "or lower"}:
        comparator = "below"
    elif modifier in {"or more", "or higher"}:
        comparator = "above"
    else:
        comparator = "exact"
    return {"kind": "cpi", "outcome": f"cpi:{comparator}:{_value_key(value)}",
            "cpi_comparator": comparator, "cpi_value": value}


# ---------------------------------------------------------------------------
# Kalshi-side parse -> the same canonical keys
# ---------------------------------------------------------------------------

def kalshi_crypto_key(market: MarketView) -> CryptoKey | None:
    """Map one Kalshi crypto strike market to a Polymarket crypto index key."""
    parsed = parse_crypto_ticker(market.ticker)
    if parsed is None or not parsed.get("asset"):
        return None
    asset = str(parsed["asset"]).upper()
    date = _utc_date_yyyymmdd(market.close_time)
    if date is None:
        return None
    strike_type = str(market.raw.get("strike_type", "")).lower()
    floor = market.raw.get("floor_strike")
    cap = market.raw.get("cap_strike")
    if strike_type in {"greater", "greater_or_equal"} and _is_number(floor):
        return (asset, "above", _strike_key(float(floor)), date)
    if strike_type == "less" and _is_number(cap):
        return (asset, "below", _strike_key(float(cap)), date)
    if strike_type == "between" and _is_number(floor) and _is_number(cap):
        low, high = sorted((float(floor), float(cap)))
        return (asset, "between", f"{_strike_key(low)}|{_strike_key(high)}", date)
    return None


def kalshi_econ_key(market: MarketView) -> EconKey | None:
    """Map one Kalshi Fed/CPI market to a Polymarket econ index key."""
    ticker = market.ticker.upper()
    month = _utc_yyyymm(market.close_time)
    if month is None:
        return None
    if ticker.startswith("KXFED"):
        outcome = _kalshi_fed_outcome(market)
        return (month, outcome) if outcome else None
    if ticker.startswith("KXCPI"):
        outcome = _kalshi_cpi_outcome(market)
        return (month, outcome) if outcome else None
    return None


def _kalshi_fed_outcome(market: MarketView) -> str | None:
    """Canonical Fed outcome from Kalshi's per-outcome sub-title fields."""
    for field in ("yes_sub_title", "yes_subtitle", "subtitle", "title"):
        text = str(market.raw.get(field, ""))
        if not text:
            continue
        low = text.lower()
        if any(word in low for word in ("no change", "unchanged", "hold", "pause")):
            return "fed:no_change:0"
        match = re.search(r"(\d+)\+?\s*bps\s*(decrease|increase|cut|hike|raise|lower)", low)
        if match is None:
            match2 = re.search(r"(decrease|increase|cut|hike|raise|lower)\s+.*?(\d+)\+?\s*bps", low)
            if match2 is None:
                continue
            bps, word = int(match2.group(2)), match2.group(1)
        else:
            bps, word = int(match.group(1)), match.group(2)
        direction = _FED_DIR.get(word)
        if direction is None:
            continue
        return f"fed:{direction}:{bps}"
    return None


def _kalshi_cpi_outcome(market: MarketView) -> str | None:
    """Canonical CPI outcome from Kalshi's strike ladder fields."""
    strike_type = str(market.raw.get("strike_type", "")).lower()
    floor = market.raw.get("floor_strike")
    cap = market.raw.get("cap_strike")
    if strike_type in {"greater", "greater_or_equal"} and _is_number(floor):
        return f"cpi:above:{_value_key(float(floor))}"
    if strike_type == "less" and _is_number(cap):
        return f"cpi:below:{_value_key(float(cap))}"
    if strike_type == "between" and _is_number(floor) and _is_number(cap):
        center = (float(floor) + float(cap)) / 2.0
        return f"cpi:exact:{_value_key(center)}"
    return None


# ---------------------------------------------------------------------------
# Signal base
# ---------------------------------------------------------------------------

class _CrossVenueMacroBase:
    """Shared discovery, CLOB midpoint, uncertainty, and diagnostics plumbing."""

    name = "cross_venue_polymarket_macro"
    _observation_source = "polymarket_macro"

    def __init__(
        self,
        fetch_markets: Callable[[], list[dict[str, Any]]] | None = None,
        fetch_orderbooks: Callable[[list[str]], dict[str, dict[str, Any]]] | None = None,
        ledger: Any = None,
    ) -> None:
        self.fetch_markets = fetch_markets or default_fetch_polymarket_markets
        self.fetch_orderbooks = (
            fetch_orderbooks if fetch_orderbooks is not None
            else default_fetch_polymarket_orderbooks
        )
        self.ledger = ledger
        self._index: dict[Any, dict[str, Any]] | None = None
        self._books: dict[str, dict[str, Any]] = {}
        self._matched = 0
        self._attempted = 0
        self._recorded: set[str] = set()

    # -- discovery -----------------------------------------------------------

    def _build_index(self, markets: list[dict[str, Any]]) -> dict[Any, dict[str, Any]]:
        raise NotImplementedError

    def on_cycle_start(self) -> None:
        self._books = {}
        self._matched = 0
        self._attempted = 0
        self._recorded = set()
        try:
            self._index = self._build_index(self.fetch_markets())
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
                pass  # Gamma outcome price remains the explicit fallback

    def _ensure_index(self) -> dict[Any, dict[str, Any]]:
        if self._index is None:
            self.on_cycle_start()
        return self._index or {}

    def diagnostics(self) -> dict[str, Any]:
        """Per-cycle match-rate transparency (partial coverage is expected)."""
        indexed = len(self._index or {})
        rate = (self._matched / self._attempted) if self._attempted else 0.0
        return {
            "source": self.name,
            "polymarket_indexed": indexed,
            "kalshi_attempted": self._attempted,
            "kalshi_matched": self._matched,
            "match_rate": round(rate, 4),
        }

    # -- pricing -------------------------------------------------------------

    def _price(self, match: dict[str, Any]) -> tuple[float, str, dict[str, float] | None]:
        """Return (p_yes, price_source, quote) from CLOB midpoint or Gamma."""
        gamma = match["prices"][0]  # outcomes = [Yes, No] -> index 0 is YES
        token_ids = match.get("token_ids") or []
        if token_ids:
            book = self._books.get(str(token_ids[0]))
            quote = _orderbook_quote(book or {}) if book else None
            if quote is not None:
                return quote["midpoint"], "clob_orderbook_midpoint", quote
        return gamma, "gamma_outcome_price", None

    def _uncertainty(
        self, match: dict[str, Any], quote: dict[str, float] | None,
    ) -> tuple[float, float]:
        if quote is not None:
            spread = quote["spread"]
        elif _is_number(match.get("best_ask")) and _is_number(match.get("best_bid")):
            spread = abs(float(match["best_ask"]) - float(match["best_bid"]))
        else:
            spread = 0.0
        liquidity = float(match.get("liquidity") or 0.0)
        thinness = 0.0 if liquidity >= 10_000 else (0.08 if liquidity >= 1_000 else 0.18)
        depth_penalty = 0.0
        if quote is not None:
            two_sided = min(quote["best_bid_size"], quote["best_ask_size"])
            depth_penalty = 0.03 if two_sided < 100 else (0.01 if two_sided < 500 else 0.0)
        return min(0.5, max(0.04, spread + thinness + depth_penalty)), spread

    def _kalshi_implied(self, market: MarketView) -> float | None:
        bid, ask = market.yes_bid, market.yes_ask
        if bid is not None and ask is not None:
            return (float(bid) + float(ask)) / 200.0
        if ask is not None:
            return float(ask) / 100.0
        if bid is not None:
            return float(bid) / 100.0
        return None

    def _emit(
        self, market: MarketView, match: dict[str, Any], p_yes: float,
        price_source: str, quote: dict[str, float] | None, extra: dict[str, Any],
    ) -> Signal | None:
        if not (0.0 < p_yes < 1.0):
            return None
        self._matched += 1
        uncertainty, spread = self._uncertainty(match, quote)
        # Wide, ambiguous books get down-weighted (never abstain outright here:
        # the wide spread already inflates uncertainty for the ensemble).
        kalshi_implied = self._kalshi_implied(market)
        divergence = (p_yes - kalshi_implied) if kalshi_implied is not None else None
        features: dict[str, Any] = {
            "challenger_only": True,
            "polymarket_slug": match["slug"],
            "polymarket_liquidity": match.get("liquidity", 0.0),
            "polymarket_price_source": price_source,
            "polymarket_gamma_probability": match["prices"][0],
            "polymarket_spread": spread,
            "cross_venue_scope": self.name,
            **extra,
        }
        if quote is not None:
            features.update({f"polymarket_{k}": v for k, v in quote.items()})
        if kalshi_implied is not None:
            features["kalshi_implied_yes"] = kalshi_implied
        if divergence is not None:
            features["cross_venue_divergence"] = divergence
        self._record_observation(market, match, p_yes, kalshi_implied, divergence, spread)
        return Signal(
            source=self.name,
            market_ticker=market.ticker,
            probability_yes=min(0.98, max(0.02, p_yes)),
            uncertainty=uncertainty,
            rationale=(
                f"Polymarket {match['slug']}: yes={p_yes:.3f} source={price_source} "
                f"spread={spread:.3f} liq={match.get('liquidity', 0.0):.0f}"
                + (f" kalshi={kalshi_implied:.3f} div={divergence:+.3f}"
                   if divergence is not None else "")
            ),
            features=features,
        )

    def _record_observation(
        self, market: MarketView, match: dict[str, Any], p_yes: float,
        kalshi_implied: float | None, divergence: float | None, spread: float,
    ) -> None:
        recorder = getattr(self.ledger, "record_external_observation", None)
        if not callable(recorder) or market.ticker in self._recorded:
            return
        self._recorded.add(market.ticker)
        features = {
            "polymarket_slug": str(match["slug"]),
            "polymarket_probability_yes": round(float(p_yes), 6),
            "polymarket_spread": round(float(spread), 6),
            "polymarket_liquidity": round(float(match.get("liquidity") or 0.0), 4),
        }
        if kalshi_implied is not None:
            features["kalshi_implied_yes"] = round(float(kalshi_implied), 6)
        if divergence is not None:
            features["divergence"] = round(float(divergence), 6)
        try:
            recorder(
                source=self._observation_source,
                series_id=market.ticker,
                observed_at=(market.fetched_at or datetime.now(timezone.utc).isoformat()),
                value=float(p_yes),
                unit="probability",
                features=features,
            )
        except Exception:
            pass  # diagnostics must never break the hunt


# ---------------------------------------------------------------------------
# Crypto signal
# ---------------------------------------------------------------------------

class CrossVenueCryptoSignal(_CrossVenueMacroBase):
    """Polymarket crypto threshold price as a challenger voice on Kalshi crypto."""

    name = "cross_venue_polymarket_crypto"
    _observation_source = "polymarket_crypto"

    def _build_index(self, markets: list[dict[str, Any]]) -> dict[Any, dict[str, Any]]:
        return index_polymarket_crypto(markets)

    def applicable(self, market: MarketView) -> bool:
        return (
            market.vertical is Vertical.CRYPTO
            and kalshi_crypto_key(market) is not None
        )

    def generate(self, market: MarketView) -> Signal | None:
        key = kalshi_crypto_key(market)
        if key is None:
            return None
        self._attempted += 1
        match = self._ensure_index().get(key)
        if match is None:
            return None  # fail-closed: no confident cross-venue match
        p_yes, price_source, quote = self._price(match)
        extra = {
            "cross_venue_comparator": match.get("comparator"),
            "market_type": f"crypto_{match.get('comparator')}",
        }
        return self._emit(market, match, p_yes, price_source, quote, extra)


# ---------------------------------------------------------------------------
# Econ signal
# ---------------------------------------------------------------------------

class CrossVenueEconSignal(_CrossVenueMacroBase):
    """Polymarket Fed/CPI outcome price as a challenger voice on Kalshi econ."""

    name = "cross_venue_polymarket_econ"
    _observation_source = "polymarket_econ"

    def _build_index(self, markets: list[dict[str, Any]]) -> dict[Any, dict[str, Any]]:
        return index_polymarket_econ(markets)

    def applicable(self, market: MarketView) -> bool:
        return (
            market.vertical is Vertical.ECON
            and kalshi_econ_key(market) is not None
        )

    def generate(self, market: MarketView) -> Signal | None:
        key = kalshi_econ_key(market)
        if key is None:
            return None
        self._attempted += 1
        match = self._ensure_index().get(key)
        if match is None:
            return None  # fail-closed
        p_yes, price_source, quote = self._price(match)
        extra = {
            "cross_venue_outcome": match.get("outcome"),
            "market_type": str(match.get("outcome", "")).split(":", 1)[0] or "econ",
        }
        return self._emit(market, match, p_yes, price_source, quote, extra)
