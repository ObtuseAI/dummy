"""Source / subject / market-type / horizon taxonomy.

Council build-out WS-15. Trust, grading, and promotion must be PER SCOPE,
not per bare source: `crypto_spot_vol` is a different animal on a 15-minute
contract than on a daily one, and a specialist can be sharp pre-game yet
noise live. This module is the single place that maps an emitted signal to
its grading scope so the backtest's contested-Brier trackers, the strategy
miner, and (WS-14) the promotion registry all agree.

The grading scope is the tuple
``(source, subject, market_type, horizon_or_phase)``:

  * source          -- the emitted ``Signal.source`` string (NOT the registry
                       source name: one registered signal emits many source
                       strings, e.g. team_sports_intelligence -> nfl_spread,
                       nba_game_total, ...).
  * subject         -- crypto asset (BTC/ETH/SOL), sports league, or exact
                       contract series. Evidence for one subject can never
                       promote another subject.
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
    # Wave-14: the brain's own post-debate fused probability, recorded per
    # scored market so pick accuracy is measurable (autonomy/picks.py). The
    # OUTPUT of fusion, never a candidate: challenger_only=False keeps it out
    # of the promotion ladder, and fusion never reads ledger rows back.
    "fused_forecast": "fused",
    "sports_elo": "sports_elo",
    # Wave-56: Glicko-2 challenger priced off the history lake. Same game-winner
    # home as Elo, graded head-to-head under its own scope (challenger-only).
    "sports_glicko": "sports_elo",
    # Wave-56: Pythagenpat challenger (scoring-margin strength), same home.
    "sports_pythagorean": "sports_elo",
    "sportsbook_consensus": "sportsbook",
    # Wave-9: licensed multi-book (The Odds API) de-vig consensus. Same
    # specialist home as the single-book ESPN consensus; graded head-to-head
    # against it under its own source scope (challenger-only).
    "licensed_consensus": "sportsbook",
    # Wave-30: market-pressure challenger -- reads multi-book line MOVEMENT
    # (steam / reverse line movement / dispersion) off the same book data.
    # Same sportsbook home; challenger-only, its own grading scope.
    "market_pressure": "sportsbook",
    "cross_venue_polymarket": "cross_venue",
    # Wave-2 E4: Polymarket cross-venue reference pricing extended to crypto and
    # econ Kalshi markets. Separate source names -> separate grading scopes; the
    # sports scope's earned champion status is NOT inherited (challenger-only).
    "cross_venue_polymarket_crypto": "cross_venue",
    "cross_venue_polymarket_econ": "cross_venue",
    "commodities_spot_vol": "commodities",
    "weather_openmeteo": "weather",
    "llm_debate": "llm",      # historical emitted source (present in old rows)
    "llm_analyst": "llm",     # current signal name, should it ever register
    # Registered signal objects whose emitted source strings differ; kept so
    # the registry-completeness tripwire resolves the registry name too.
    "mlb_intelligence": "mlb",
    "team_sports_intelligence": "team_sports",
    # Wave-10 licensed prop signal's registry name; its emitted sources are
    # licensed_prop_<stat> (covered by the prefix rule below).
    "licensed_player_prop": "sportsbook",
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
    # Wave-12: WNBA joins the routed team leagues (TeamLeagueSpecialist).
    "wnba": "wnba",
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
    # The REGISTERED signal object's own name (PowerRatingsSignal.name ==
    # "power_ratings", no league suffix -- the league only appears on the
    # emitted Signal.source strings mapped just above). Kept for the same
    # reason as "mlb_intelligence"/"team_sports_intelligence": so the
    # registry-completeness tripwire resolves the bare registry name too.
    "power_ratings": "power_ratings",
    # Fantasy leg #1: FanGraphs projection consensus prices MLB winner/total
    # markets, so the MLB specialist owns its record. Exact entry (like
    # "mlb_intelligence") because the source is named for its data source,
    # not the league prefix.
    "fangraphs_projection_consensus": "mlb",
    # Fantasy leg #3: ESPN fantasy (flb) crowd lean prices MLB winner markets,
    # so the MLB specialist owns its record. Exact entry (like
    # "fangraphs_projection_consensus") because the source is named for its data
    # source, not the league prefix.
    "espn_fantasy_crowd": "mlb",
    # Wave-22: the Universal Sports Engine sidecar challenger. Per-league
    # emitted sources route to the league specialists (power_ratings
    # precedent: exact entries, one prefix cannot fan out per league); the
    # bare registry name resolves for the completeness tripwire.
    "use_sim": "use_sim",
    "use_sim_mlb": "mlb",
    "use_sim_nba": "nba",
    "use_sim_wnba": "wnba",
    "use_sim_nfl": "nfl",
    "use_sim_ncaaf": "ncaaf",
    "use_sim_ncaamb": "ncaamb",
    "use_sim_nhl": "nhl",
}

# (prefix, specialist) resolved in order; the first match wins. Ordering only
# matters when one prefix is a prefix of another (none are here).
_SPECIALIST_PREFIXES: tuple[tuple[str, str], ...] = (
    ("crypto_", "crypto"),
    # Licensed player props (licensed_prop_<stat>) are the sportsbook-consensus
    # family, same home as licensed_consensus (Wave-10).
    ("licensed_prop_", "sportsbook"),
    # Wave-11 line-market sub-sources (licensed_consensus_total/_spread) share
    # the sportsbook home; the bare "licensed_consensus" winner source stays an
    # exact SOURCE_TAXONOMY entry above.
    ("licensed_consensus_", "sportsbook"),
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

_SPORTS_SUBJECT_PREFIXES: tuple[tuple[str, str], ...] = (
    ("KXNCAAMB", "ncaamb"),
    ("KXNCAAF", "ncaaf"),
    ("KXWNBA", "wnba"),
    ("KXNBA", "nba"),
    ("KXNFL", "nfl"),
    ("KXNHL", "nhl"),
    ("KXMLB", "mlb"),
)


def specialist_for(source: str) -> str:
    """Specialist label for an emitted source string; 'other' when unmapped.

    The registry-completeness tripwire test asserts no REGISTERED source ever
    resolves to 'other' -- that is the alarm when a new signal ships without
    a taxonomy home.
    """
    name = str(source or "")
    # WS-18 calibrated shadows ("{source}::cal") are monotone transforms of
    # their parent: same specialist home, own grading scope.
    if name.endswith("::cal"):
        name = name[:-5]
    if name in SOURCE_TAXONOMY:
        return SOURCE_TAXONOMY[name]
    for prefix, label in _SPECIALIST_PREFIXES:
        if name.startswith(prefix):
            return label
    return "other"


def prediction_subject(ticker: str) -> str:
    """Return the exact asset, league, or contract-series subject.

    Promotion evidence must not pool BTC with ETH, MLB with NFL, or any
    otherwise unrelated contract series. Unknown series remain isolated under
    their normalized series token instead of falling into one global bucket.
    """
    normalized = str(ticker or "").strip().upper()
    parsed = parse_crypto_ticker(normalized)
    if parsed is not None and parsed.get("asset"):
        return str(parsed["asset"]).lower()
    for asset in ("BTC", "ETH", "SOL"):
        if normalized.startswith(f"KX{asset}"):
            return asset.lower()
    for prefix, subject in _SPORTS_SUBJECT_PREFIXES:
        if normalized.startswith(prefix):
            return subject
    series = normalized.split("-", 1)[0]
    return series.lower() if series else "unknown"


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
    """The full ``source|subject|market_type|horizon_or_phase`` key.

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
    return f"{source}|{prediction_subject(ticker)}|{market_type}|{axis}"


def scope_weight_key(
    source: str, ticker: str, features: dict[str, Any] | None,
) -> str:
    """Persistent trust-key for one exact grading scope.

    The ``scope:`` namespace cannot collide with historical bare-source or
    ``source@VERTICAL`` trust rows.  Keeping this convention beside
    ``grading_scope`` prevents the learner, forecaster, and backtest bootstrap
    from inventing subtly different keys.
    """
    return f"scope:{grading_scope(source, ticker, features or {})}"
