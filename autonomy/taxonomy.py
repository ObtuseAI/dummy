"""Source / market-type / horizon taxonomy — one grading-scope vocabulary.

Council build-out WS-15. Trust, grading, and promotion must be PER SCOPE,
not per bare source: `crypto_spot_vol` is a different animal on a 15-minute
contract than on a daily one, and a specialist can be sharp pre-game yet
noise live. This module is the single place that maps an emitted signal to
its grading scope so the backtest's contested-Brier trackers, the strategy
miner, and (WS-14) the promotion registry all agree.

The grading scope is the triple ``(source, market_type, horizon_or_phase)``:

  * source          -- the emitted ``Signal.source`` string (NOT the registry
                       source name: one registered signal emits many source
                       strings, e.g. team_sports_intelligence -> nfl_spread,
                       nba_game_total, ...).
  * market_type     -- winner / spread / total / yrfi (sports, already stamped
                       in features) or the crypto contract family.
  * horizon_or_phase-- crypto: 15m / hourly / daily+ ; sports: pre / live.

Horizon is derived from the emission-time ``hours_to_close`` that crypto
signals already persist in their features, so it is point-in-time correct
(the horizon reflects when the opinion was formed, never re-derived against a
later clock) AND works on historical rows that predate any explicit stamp.
"""
from __future__ import annotations

from typing import Any

from autonomy.signals.crypto_spot import parse_crypto_ticker

# Crypto contracts closing within this many hours grade as the "hourly"
# scope; longer-dated ones as "daily+". The native 15-minute series is
# detected by ticker and bypasses this threshold.
CRYPTO_HOURLY_MAX_HOURS = 3.0

# Exact emitted-source (and registry-name) -> specialist label. Sub-sources
# that carry a league/asset prefix (mlb_*, nfl_*, crypto_*, ...) resolve via
# ``specialist_for``'s prefix rules instead of being enumerated here.
SOURCE_TAXONOMY: dict[str, str] = {
    "market_prior": "market",
    "market_debias": "market",
    "sports_elo": "sports_elo",
    "sportsbook_consensus": "sportsbook",
    "cross_venue_polymarket": "cross_venue",
    "commodities_spot_vol": "commodities",
    "weather_openmeteo": "weather",
    "llm_debate": "llm",      # historical emitted source (present in old rows)
    "llm_analyst": "llm",     # current signal name, should it ever register
    # Registered signal objects whose emitted source strings differ; kept so
    # the registry-completeness tripwire resolves the registry name too.
    "mlb_intelligence": "mlb",
    "team_sports_intelligence": "team_sports",
    # WS-8: idempotent self-mappings for the council's OWN routing labels
    # (autonomy.specialists.base.Specialist.name -- e.g. MlbSpecialist.name
    # == "mlb", TeamLeagueSpecialist.name == the league string). The
    # mispricing monitor's paper entries are a fused/live forecast, not one
    # named ledger signal, so they are tagged with the routed specialist's
    # own name rather than an emitted Signal.source string; these entries
    # let specialist_for() resolve that tag through the same vocabulary
    # everything else uses instead of falling through to "other". No
    # registered SIGNAL source is ever a bare specialist label (verified by
    # test_registry_completeness_tripwire), so this is collision-free.
    "mlb": "mlb",
    "crypto": "crypto",
    "nba": "nba",
    "nfl": "nfl",
    "ncaaf": "ncaaf",
    "nhl": "nhl",
    "ncaamb": "ncaamb",
    # WS-A2 (Phenon Harness): the power-ratings challenger emits
    # "power_ratings_<league>" per league (autonomy/signals/
    # sports_intelligence.py::PowerRatingsSignal) -- exact entries, not a
    # prefix rule, since one "power_ratings_" prefix cannot resolve to
    # per-league labels the way the existing (prefix, single-label) tuples
    # in _SPECIALIST_PREFIXES do. Collision-free: no other registered
    # source or self-mapping starts with "power_ratings_".
    "power_ratings_nfl": "nfl",
    "power_ratings_ncaaf": "ncaaf",
    "power_ratings_nba": "nba",
    "power_ratings_ncaamb": "ncaamb",
}

# (prefix, specialist) resolved in order; the first match wins. Ordering only
# matters when one prefix is a prefix of another (none are here).
_SPECIALIST_PREFIXES: tuple[tuple[str, str], ...] = (
    ("crypto_", "crypto"),
    ("mlb_", "mlb"),
    ("nfl_", "nfl"),
    ("ncaaf_", "ncaaf"),
    ("ncaamb_", "ncaamb"),
    ("nba_", "nba"),
    ("nhl_", "nhl"),
    ("wnba_", "wnba"),
    ("ufc_", "retired"),
    ("f1_", "retired"),
)


def specialist_for(source: str) -> str:
    """Specialist label for an emitted source string; 'other' when unmapped.

    The registry-completeness tripwire test asserts no REGISTERED source ever
    resolves to 'other' -- that is the alarm when a new signal ships without
    a taxonomy home.
    """
    name = str(source or "")
    if name in SOURCE_TAXONOMY:
        return SOURCE_TAXONOMY[name]
    for prefix, label in _SPECIALIST_PREFIXES:
        if name.startswith(prefix):
            return label
    return "other"


def horizon_bucket(ticker: str, hours_to_close: float | None) -> str:
    """Crypto horizon scope: '15m' | 'hourly' | 'daily+' | 'unknown'.

    15-minute contracts are recognized from the series token (robust to
    whether the ticker parses); everything else splits on the emission-time
    hours-to-close. Unknown when no horizon evidence exists (fail-open to a
    single bucket rather than a wrong one).
    """
    series = str(ticker or "").split("-", 1)[0].upper()
    if "15M" in series:
        return "15m"
    if hours_to_close is None:
        return "unknown"
    try:
        hours = float(hours_to_close)
    except (TypeError, ValueError):
        return "unknown"
    return "hourly" if hours <= CRYPTO_HOURLY_MAX_HOURS else "daily+"


def market_type_for(source: str, ticker: str, features: dict[str, Any] | None) -> str:
    """Market family for the grading scope.

    Sports signals already stamp ``market_type`` in features (winner / spread
    / total / total_runs / yrfi); crypto derives its contract family from the
    ticker; anything else is 'na'.
    """
    features = features or {}
    stamped = features.get("market_type")
    if stamped:
        return str(stamped)
    parsed = parse_crypto_ticker(str(ticker or ""))
    if parsed is not None:
        return str(parsed.get("contract_family") or "crypto")
    return "na"


def _phase(source: str, features: dict[str, Any] | None) -> str:
    features = features or {}
    if "live" in str(source or "") or features.get("live"):
        return "live"
    return "pre"


def grading_scope(source: str, ticker: str, features: dict[str, Any] | None) -> str:
    """The full ``source|market_type|horizon_or_phase`` grading key.

    Crypto scopes on horizon (a source prices every horizon under one name);
    sports and everything else scope on phase (pre/live). Deterministic and
    pure -- the same inputs always yield the same key so trackers accrete
    consistently across runs.
    """
    features = features or {}
    market_type = market_type_for(source, ticker, features)
    if specialist_for(source) == "crypto":
        axis = horizon_bucket(ticker, features.get("hours_to_close"))
    else:
        axis = _phase(source, features)
    return f"{source}|{market_type}|{axis}"
