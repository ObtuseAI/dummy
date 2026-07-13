"""Power-ratings fetch + consensus core (Phenon Harness WS-A1).

Pure, point-in-time module: fetches/parses public keyless power-index
ratings (ESPN FPI for football, ESPN BPI for basketball) and blends them
with the existing point-in-time EloModel into a single ensemble margin
estimate.

Point-in-time discipline: ratings here are READ ONLY. They are consumed
for pricing and NEVER fed back into any model's update()/learning path.
`EloSource` wraps `EloModel.rating()` (a pure read) and must never call
`.update()` -- there is no code path in this module that does.

Fail-closed at every layer: a down/malformed feed, missing team, or
off-season empty payload all resolve to that source dropping out silently
(no raise, no crash). If every source drops out, `consensus_margin`
returns `None`, byte-identical to the feature simply being absent --
callers must treat `None` as "no signal" exactly like every other
optional feature in this codebase.

No scraping: FPI/BPI are ESPN's public keyless JSON APIs (the same class
of first-party endpoint already used by `autonomy.sports.espn` /
`autonomy.sports.ballpark_weather`), not an HTML scrape.

FPI JSON path (probed 2026-07-13 against
`https://site.web.api.espn.com/apis/fitt/v3/sports/football/nfl/powerindex?limit=1000`,
HTTP 200, keyless): the team key is `teams[N].team.abbreviation`; the
rating value is `teams[N].categories[C].values[0]` where category `C` is
the entry with `"name": "fpi"` (the top-level `glossary`/`categories`
blocks confirm `names[0] == "fpi"`, labeled "FPI" -- "Football Power
Index ... expected point margin vs average opponent on neutral field", so
FPI is already reported on an approximately point-margin scale). Trimmed
fixture (6 teams): `tests/fixtures/espn_fpi_nfl_powerindex_probe.json`.

BPI JSON path (same probe session, same date, against
`.../basketball/nba/powerindex?limit=1000`, HTTP 200, keyless, 30 teams
returned): identical shape; the rating category name is `"bpi"` instead
of `"fpi"`, `values[0]` is the Basketball Power Index rating. Trimmed
fixture (6 teams): `tests/fixtures/espn_bpi_nba_powerindex_probe.json`.
`ncaamb`/`college-football` powerindex endpoints were also probed keyless
200 this session (365 / 138 teams respectively) but no fixture was
committed for them since FPI/BPI share one parser and one JSON shape.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable

from autonomy.sports.espn import LEAGUE_TO_ESPN, canonical_team

_BASE_URL = "https://site.web.api.espn.com/apis/fitt/v3/sports"


@runtime_checkable
class RatingSource(Protocol):
    """A point-in-time power-rating provider. Never mutates any model."""

    name: str

    def rating(self, league: str, team: str) -> float | None:
        """Team's rating, or None if the source has no opinion this cycle."""
        ...


# Per-league scale converting one native rating unit into expected point
# margin. Propose-then-promote TUNER CANDIDATES (same convention as
# nfl_margin.BASE_ABS_MARGIN_PMF / nba_model's heteroskedastic sigmas):
# picked as reasonable starting points, never independently fit.
#
# These values are calibrated to EloModel's native scale (SCALE=400
# logistic, ratings centered on BASE_RATING=1500) converted to point
# margin using widely-cited rule-of-thumb ratios: ~25 Elo points per
# point of NFL/NCAAF margin, ~28 Elo points per point of NBA/NCAAMB
# margin.
#
# KNOWN SIMPLIFICATION: ESPN's FPI/BPI are already reported on an
# approximately point-margin scale ("expected point margin vs average
# opponent" per ESPN's own glossary), so applying this SAME per-league
# factor to an FPI/BPI source's rating diff will shrink its implied
# margin by roughly this same factor rather than leaving it near 1:1.
# WS-A1's exact signature specifies one constant per league (not one per
# source x league), so per-source scale separation is deferred to the
# tuner once there is contested-Brier evidence to justify a promotion.
POINTS_PER_RATING_UNIT: dict[str, float] = {
    "nfl": 25.0,
    "ncaaf": 25.0,
    "nba": 28.0,
    "ncaamb": 28.0,
}

# ESPN sport -> the powerindex category holding the headline rating.
_CATEGORY_NAME_BY_SPORT: dict[str, str] = {
    "football": "fpi",
    "basketball": "bpi",
}


def default_fetch_powerindex(league: str) -> dict:
    """Keyless ESPN powerindex fetch for `league`.

    Mirrors the httpx GET + timeout + raise_for_status idiom used by
    `autonomy.sports.ballpark_weather.default_fetch_hourly_weather`.
    Reuses `LEAGUE_TO_ESPN` (autonomy.sports.espn) for the league -> ESPN
    sport/path mapping rather than hardcoding a second copy.
    """
    import httpx

    mapping = LEAGUE_TO_ESPN.get(league)
    if mapping is None:
        # Unmapped league: fail closed (empty payload) rather than raising
        # KeyError on a direct caller. `_CachedPowerIndexSource.rating` also
        # wraps this in try/except, but that shouldn't be the only thing
        # standing between an unmapped league and an unhandled exception.
        return {}
    sport, espn_league = mapping
    response = httpx.get(
        f"{_BASE_URL}/{sport}/{espn_league}/powerindex",
        params={"limit": 1000},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def parse_powerindex(payload: Any, league: str) -> dict[str, float]:
    """Team-abbreviation -> FPI/BPI rating. Defensive: never raises.

    The rating category is `"fpi"` for football leagues and `"bpi"` for
    basketball leagues (see module docstring for the confirmed JSON
    path). Any entry missing a usable team abbreviation, categories
    array, matching category, or numeric value is skipped rather than
    raising. A malformed/short/empty payload (not a dict, no `teams`
    list, etc.) returns `{}`.
    """
    if not isinstance(payload, dict):
        return {}
    teams = payload.get("teams")
    if not isinstance(teams, list):
        return {}

    sport = LEAGUE_TO_ESPN.get(league, (None, None))[0]
    category_name = _CATEGORY_NAME_BY_SPORT.get(sport, "fpi")

    ratings: dict[str, float] = {}
    for entry in teams:
        if not isinstance(entry, dict):
            continue
        team = entry.get("team")
        if not isinstance(team, dict):
            continue
        abbr = team.get("abbreviation")
        if not isinstance(abbr, str) or not abbr:
            continue
        categories = entry.get("categories")
        if not isinstance(categories, list):
            continue
        category = next(
            (c for c in categories if isinstance(c, dict) and c.get("name") == category_name),
            None,
        )
        if category is None:
            continue
        values = category.get("values")
        if not isinstance(values, list) or not values:
            continue
        value = values[0]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        ratings[canonical_team(league, abbr)] = float(value)
    return ratings


class _CachedPowerIndexSource:
    """Shared fetch/cache/fail-closed plumbing for FPI and BPI sources.

    Caches the parsed per-league rating map for the life of this
    instance (i.e. per trading cycle -- callers construct a fresh source
    each cycle, matching the pattern other per-cycle-warmed signals in
    this repo already use). A fetch or parse failure caches an empty map
    for that league so every team resolves to None that cycle instead of
    raising.

    Deliberately declares no `name` here: `consensus_margin`'s `per_source`
    dict is keyed by `source.name`, so a shared default across subclasses
    would silently collide (two sources overwriting one entry, undercounting
    `n_sources`) instead of failing loudly. Each concrete subclass MUST set
    its own distinct `name`.
    """

    def __init__(self, fetch: Callable[[str], dict] | None = None) -> None:
        self._fetch = fetch or default_fetch_powerindex
        self._cache: dict[str, dict[str, float]] = {}

    def rating(self, league: str, team: str) -> float | None:
        if league not in self._cache:
            try:
                payload = self._fetch(league)
                self._cache[league] = parse_powerindex(payload, league)
            except Exception:
                self._cache[league] = {}
        return self._cache[league].get(canonical_team(league, team))


class EspnFpiSource(_CachedPowerIndexSource):
    """ESPN Football Power Index (keyless, first-party)."""

    name = "espn_fpi"


class EspnBpiSource(_CachedPowerIndexSource):
    """ESPN Basketball Power Index (keyless, first-party)."""

    name = "espn_bpi"


class EloSource:
    """Wraps an already-warm EloModel as a read-only RatingSource.

    Only ever calls `elo_model.rating(team)` (a pure read). Never calls
    `.update()` -- point-in-time ratings must not leak into the model's
    learning path.

    `EloModel.rating` (autonomy/sports/elo.py) is `self.ratings.get(team,
    BASE_RATING)` -- it fabricates BASE_RATING (1500.0) for ANY unknown
    team and never returns None. To stay fail-closed, membership in the
    model's rating table is checked directly (`team in elo_model.ratings`)
    BEFORE calling `.rating()`, rather than calling `.rating()` and
    comparing the result to 1500.0 -- a team can be legitimately rated
    exactly 1500.0, and that must not be mistaken for "missing".
    """

    name = "elo"

    def __init__(self, elo_model: Any) -> None:
        self._elo_model = elo_model

    def rating(self, league: str, team: str) -> float | None:
        key = canonical_team(league, team)
        if key not in self._elo_model.ratings:
            return None
        return self._elo_model.rating(key)


@dataclass(frozen=True)
class ConsensusMargin:
    ensemble_margin: float
    dispersion: float
    n_sources: int
    per_source: dict[str, float]


def consensus_margin(
    home: str, away: str, league: str, sources: list[RatingSource]
) -> ConsensusMargin | None:
    """Blend every source's implied point margin into one consensus.

    For each source where BOTH teams resolve to a rating, the implied
    margin is `(rating(home) - rating(away)) * POINTS_PER_RATING_UNIT[league]`.
    `ensemble_margin` is the median of the implieds, `dispersion` is
    max - min (0.0 for a single source). Zero implieds (no sources, an
    unknown league, or every source dropping out) returns None. No side
    effects; nothing here ever touches a model's learning path.
    """
    scale = POINTS_PER_RATING_UNIT.get(league)
    if scale is None:
        return None

    per_source: dict[str, float] = {}
    for source in sources:
        home_rating = source.rating(league, home)
        away_rating = source.rating(league, away)
        if home_rating is None or away_rating is None:
            continue
        per_source[source.name] = (home_rating - away_rating) * scale

    if not per_source:
        return None

    implieds = list(per_source.values())
    ensemble_margin = statistics.median(implieds)
    dispersion = (max(implieds) - min(implieds)) if len(implieds) > 1 else 0.0
    return ConsensusMargin(
        ensemble_margin=ensemble_margin,
        dispersion=dispersion,
        n_sources=len(implieds),
        per_source=per_source,
    )
