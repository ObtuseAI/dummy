"""Prediction-target policy shared by forecasting, boards, and execution.

Weather and commodity feeds are contextual data sources only.  They may inform
sports and crypto models, but their contracts are never forecast, ranked as a
bet, paper traded, or submitted to a broker.

Stock and cash-index contracts are outside Dummy's active prediction surface.
They are denied by structured category evidence and a narrow list of known
contract-series prefixes.  Caller assertions can never promote one of these
targets.  Titles and free-form descriptions are deliberately ignored.
"""
from __future__ import annotations

from typing import Any

from autonomy.ontology import Vertical


TARGET_POLICY_VERSION = "prediction_target_v4_crypto_sports_only"


DATA_ONLY_VERTICALS: frozenset[Vertical] = frozenset({
    Vertical.WEATHER,
    Vertical.COMMODITIES,
})

_DATA_ONLY_TICKER_PREFIXES: tuple[str, ...] = (
    "WEATHER",
    "KXHIGH",
    "KXLOW",
    "KXRAIN",
    "KXSNOW",
    "COMMODITY",
    "KXOIL",
    "KXWTI",
    "KXNATGAS",
    "KXNGAS",
    "KXGAS",
    "KXGOLD",
)

# Defence-in-depth for known Kalshi equity and cash-index series, plus the
# corresponding bare identifiers found in legacy stored forecast rows.  This
# is intentionally a bounded deny-list, not a claim that ticker strings are
# complete category metadata.  The live sink also evaluates independently
# fetched market -> event -> series category metadata.
EQUITY_INDEX_TICKER_PREFIXES: tuple[str, ...] = (
    # Cash/equity index series.
    "KXINXY",
    "KXINX",
    "KXSPX",
    "KXSP500",
    "KXNASDAQ100Y",
    "KXNASDAQ100",
    "KXNASDAQ",
    "KXNDX",
    "KXDJI",
    "KXDOW",
    "KXRUT",
    "KXIPO",
    # Single-name equity series observed or explicitly supported by legacy UI.
    "KXTSLAA",
    "KXTSLA",
    "KXAAPLA",
    "KXAAPL",
    "KXNVDAA",
    "KXNVDA",
    "KXAMZNA",
    "KXAMZN",
    # Current company-KPI series whose venue category is ``Companies`` rather
    # than ``Financials``.  Keep these exact-series guards for early paths that
    # only have a market ticker; the final firewall additionally rechecks the
    # independently fetched event/series category and tags.
    "KXBAA",
    "KXEBAYA",
    "KXCVNAA",
    "KXFA",
    "KXUALA",
    "KXMETA",
    "KXMSFT",
    "KXGOOGL",
    "KXGOOG",
    "KXCOIN",
    "KXMSTR",
    # Stored/local identifiers (boundary-matched below).
    "SPX",
    "INX",
    "SP500",
    "NDX",
    "NASDAQ100",
    "NASDAQ",
    "QQQ",
    "DJI",
    "DOW",
    "RUT",
    "SPY",
    "TSLA",
    "AAPL",
    "NVDA",
    "AMZN",
    "META",
    "MSFT",
    "GOOGL",
    "GOOG",
    "COIN",
    "MSTR",
)

_EQUITY_INDEX_CATEGORIES: frozenset[str] = frozenset({
    "equity",
    "equities",
    "company",
    "companies",
    "stock",
    "stocks",
    "index",
    "indices",
})

# Kalshi's broad ``Financials`` category also contains foreign exchange,
# interest-rate, and other non-equity contracts.  Only these exact series tags,
# when supplied by the independently verified venue hierarchy, strengthen the
# quarantine.  Caller/strategy metadata can only cause a denial; it can never
# confer prediction or execution authority.
_EQUITY_INDEX_SERIES_TAGS: frozenset[str] = frozenset({
    "company",
    "companies",
    "index",
    "indices",
    "ipo",
    "ipos",
    "kpi",
    "kpis",
    "single company",
    "stock",
    "stocks",
})

# A structured venue category or a typed autonomy vertical may establish that
# a non-quarantined contract is an intended prediction target.  Keep this an
# allow-list: a new/opaque category is unknown authority until it is reviewed,
# not permission merely because it is absent from the deny lists above.
#
# Wave-85: elections / politics / economic / economics / macro / entertainment
# were removed. Three layers had been stating three different intents:
#   * this list GRANTED prediction-target authority to all six,
#   * configs/caps.json blocks categories ["Elections", "Politics"],
#   * the scanner never fetches any of them and scan() filters to
#     {CRYPTO, SPORTS}.
# The system failed closed because the blocks won, so nothing was ever traded
# on that authority -- but "harmless because a different layer stops it" is
# exactly the arrangement that turns into a live incident the first time the
# stopping layer moves. The allow-list now says the same thing the caps file
# and the scanner already say, so the intent is stated once.
#
# This is deliberately narrower than "whatever Kalshi lists": econ and
# commodities trading was retired 2026-07-11 for never demonstrating an edge,
# and no politics/elections pricing path was ever built.
_PREDICTION_TARGET_CATEGORIES: frozenset[str] = frozenset({
    "crypto",
    "cryptocurrency",
    "cryptocurrencies",
    "sports",
})

_PREDICTION_TARGET_VERTICALS: frozenset[Vertical] = frozenset({
    Vertical.CRYPTO,
    Vertical.SPORTS,
})


def _normalise_category(category: Any) -> str:
    return " ".join(str(category or "").strip().casefold().replace("_", " ").split())


def _normalise_tags(series_tags: Any) -> frozenset[str]:
    if not isinstance(series_tags, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(
        normalised
        for value in series_tags
        if (normalised := _normalise_category(value))
    )


def _matches_ticker_prefix(ticker: str, prefixes: tuple[str, ...]) -> bool:
    """Match a series identifier without loose substring/title inference.

    Kalshi contract tickers append a dash or numeric cadence/date suffix to a
    series ticker.  Stored observations also use ``_`` and ``:`` separators.
    Requiring one of those boundaries avoids classifying unrelated symbols
    merely because they share the first few letters.
    """
    upper = str(ticker or "").strip().upper()
    for prefix in prefixes:
        if upper == prefix:
            return True
        if not upper.startswith(prefix):
            continue
        remainder = upper[len(prefix):]
        if remainder and (remainder[0].isdigit() or remainder[0] in "-_:"):
            return True
    return False


def is_data_only_vertical(vertical: Any) -> bool:
    """Return True for the two verticals that can supply data but not targets."""
    try:
        value = vertical if isinstance(vertical, Vertical) else Vertical(str(vertical).upper())
    except (TypeError, ValueError):
        return False
    return value in DATA_ONLY_VERTICALS


def is_data_only_target(
    ticker: str = "",
    *,
    category: str | None = None,
    vertical: Any | None = None,
) -> bool:
    """Classify a direct weather/commodity contract without using its title.

    Titles are deliberately ignored because sports titles can mention weather
    and macro commentary can mention oil or gold.  Structured vertical,
    category, and known contract prefixes are stable target identifiers.
    """
    if vertical is not None and is_data_only_vertical(vertical):
        return True
    normalized_category = _normalise_category(category)
    if normalized_category in {"weather", "commodity", "commodities"}:
        return True
    upper = str(ticker or "").strip().upper()
    return any(upper.startswith(prefix) for prefix in _DATA_ONLY_TICKER_PREFIXES)


def is_equity_index_target(
    ticker: str = "",
    *,
    category: str | None = None,
    vertical: Any | None = None,
    series_tags: Any | None = None,
) -> bool:
    """Return whether the target is outside the supported prediction surface.

    ``vertical`` is accepted for the shared call signature, but the current
    autonomy ontology has no EQUITY member.  ECON is *not* treated as equity:
    CPI/Fed/GDP markets must not be mislabeled as stocks.  Structured category
    metadata and exact series-prefix matches are the authoritative inputs.
    """
    del vertical
    if _normalise_category(category) in _EQUITY_INDEX_CATEGORIES:
        return True
    if _normalise_tags(series_tags) & _EQUITY_INDEX_SERIES_TAGS:
        return True
    return _matches_ticker_prefix(ticker, EQUITY_INDEX_TICKER_PREFIXES)


def is_prediction_quarantined_target(
    ticker: str = "",
    *,
    category: str | None = None,
    vertical: Any | None = None,
    series_tags: Any | None = None,
) -> bool:
    """Return True when a target has zero forecast/proposal/execution authority."""
    return is_data_only_target(ticker, category=category, vertical=vertical) or (
        is_equity_index_target(
            ticker,
            category=category,
            vertical=vertical,
            series_tags=series_tags,
        )
    )


def has_prediction_target_authority(
    ticker: str = "",
    *,
    category: str | None = None,
    vertical: Any | None = None,
    series_tags: Any | None = None,
) -> bool:
    """Return whether trusted structured context authorizes this target.

    Tickers are checked only for deny-side defence in depth.  Positive
    authority comes from a typed ``MarketView`` vertical or a structured venue
    category.  This means an opaque company ticker cannot enter the paper book
    merely because its string is not yet in a prefix list, while the scanner's
    verified SPORTS/CRYPTO markets continue normally.
    """
    if is_prediction_quarantined_target(
        ticker,
        category=category,
        vertical=vertical,
        series_tags=series_tags,
    ):
        return False
    if _normalise_category(category) in _PREDICTION_TARGET_CATEGORIES:
        return True
    try:
        typed_vertical = (
            vertical
            if isinstance(vertical, Vertical)
            else Vertical(str(vertical).strip().upper())
        )
    except (TypeError, ValueError):
        return False
    return typed_vertical in _PREDICTION_TARGET_VERTICALS


def target_policy_payload(
    ticker: str = "",
    *,
    category: str | None = None,
    vertical: Any | None = None,
    series_tags: Any | None = None,
) -> dict[str, Any]:
    """Backend-authored target classification; informational, never authority.

    The default is explicitly unverified rather than allowed.  Execution still
    requires every independent strategy, compliance, risk, and firewall gate.
    """
    if is_data_only_target(ticker, category=category, vertical=vertical):
        return {
            "policy_version": TARGET_POLICY_VERSION,
            "classification": "data_only",
            "role": "data_only",
            "prediction_target": False,
            "trade_proposal_authority": False,
            "execution_target": False,
            "reason": "weather_and_commodities_are_context_only",
        }
    if is_equity_index_target(
        ticker,
        category=category,
        vertical=vertical,
        series_tags=series_tags,
    ):
        return {
            "policy_version": TARGET_POLICY_VERSION,
            "classification": "unsupported_target",
            "role": "excluded",
            "prediction_target": False,
            "trade_proposal_authority": False,
            "execution_target": False,
            "reason": "outside_supported_prediction_targets",
        }
    if has_prediction_target_authority(
        ticker,
        category=category,
        vertical=vertical,
        series_tags=series_tags,
    ):
        return {
            "policy_version": TARGET_POLICY_VERSION,
            "classification": "prediction_target_authorized",
            "role": "prediction_target",
            "prediction_target": True,
            "trade_proposal_authority": True,
            "execution_target": True,
            "reason": "structured_target_context_authorized",
        }
    return {
        "policy_version": TARGET_POLICY_VERSION,
        "classification": "eligibility_unverified",
        "role": "eligibility_unverified",
        "prediction_target": None,
        "trade_proposal_authority": None,
        "execution_target": None,
        "reason": "target_not_classified_by_this_policy",
    }


DATA_ONLY_CONTEXT_POLICY = {
    "weather": {
        "role": "data_only",
        "prediction_target": False,
        "execution_target": False,
        "consumers": ["sports_weather_adjustments"],
    },
    "commodities": {
        "role": "data_only",
        "prediction_target": False,
        "execution_target": False,
        "consumers": ["crypto_macro_regime"],
    },
}
