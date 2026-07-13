"""WS-7: situational-awareness engine -- rest, playoff context, suspensions,
roster-drift -- across engines.

Same discipline as every other module in this package (WS-6's players.py is
the closest sibling; read its module docstring first):

  * Challenger-only: every consumer of this module sets
    ``features["challenger_only"] = True`` on the emitted Signal (done in
    autonomy/signals/sports_intelligence.py, not here).
  * Fail-closed: no feed / unreachable / offseason -> zero effect, BYTE-
    IDENTICAL to this whole layer being disabled. Every public entry point
    below degrades to a genuine no-op on missing/malformed input rather than
    guessing.
  * Point-in-time: the only state this module accumulates across cycles
    (``GameDateTracker``, ``RosterDriftBook``) learns exclusively from
    ``game.status == "post"`` (settlement) or from the CURRENT roster
    snapshot compared to a PRIOR cycle's snapshot -- never from a live/in-
    progress game.
  * HARD verifiable states (rest) -> a bounded MEAN adjustment on the
    affected team's expected margin, per the constants table below. SOFT/
    narrative states (playoff motivation, roster/coaching churn) -> WIDEN
    UNCERTAINTY ONLY; the mean is byte-identical to the state's absence.
    This split is the single most important correctness property in this
    module (mirrors players.py's HARD/SOFT split) -- every soft-state helper
    below returns an uncertainty delta and NEVER a margin delta.
  * Every state is logged into the returned dataclasses' ``features`` dict
    for the miner (autonomy/signals/sports_intelligence.py merges these
    verbatim into the emitted Signal.features).

SCOPE DECISION -- NBA's rest engine is untouched: ``autonomy/sports/
nba_model.py`` already ships a MERGED+TESTED, in-model rest engine
(``rest_days_since``/``rest_adjustment``, 35 passing tests) that NBA's
``NbaModel.predict`` calls directly. Ripping that out to route through a
new shared tracker risks the working NBA path for zero behavior change, so
it is deliberately left exactly as-is (per this workstream's own brief: "if
there's any doubt, DON'T"). What this module builds is a SEPARATE, GENERIC
per-team game-date-history tracker (``GameDateTracker``) for the leagues
that do NOT already have one: NFL (bye / Thursday short week) and NHL
(back-to-back). The date-arithmetic helpers below (``_parse_date``,
``rest_days_since``) are intentionally a small, independent duplicate of
nba_model.py's identically-named private helpers rather than an import --
seeded once when this module was small in scope, so this module has zero
runtime coupling to NBA's engine (a future change to NBA's rest engine can
never silently perturb NFL/NHL's, and vice versa). See ws7-report.md for the
explicit final-review consolidation note.

BUILD-TIME PROBES (2026-07-13, network confirmed reachable, keyless):

1. Standings/playoff-context endpoint. The brief named
   ``.../{sport}/{league}/standings`` (i.e. the SAME path shape as ESPN's
   other ``site.api.espn.com/apis/site/v2/...`` endpoints this codebase
   already uses) -- probed and confirmed that exact path returns a 86-byte
   STUB with no standings data at all: ``{"fullViewLink": {"text": "Full
   Standings", "href": "https://www.espn.com/nfl/standings"}}`` for nfl/nhl/
   nba alike. Real per-team standings live at a DIFFERENT, still-keyless
   path: ``https://site.api.espn.com/apis/v2/sports/{sport}/{league}/
   standings`` (``apis/v2/...``, not ``apis/site/v2/...``) -- confirmed 200
   with real per-team ``stats`` arrays (wins/losses/gamesBehind/playoffSeed/
   streak/...) for nfl (32 teams), nhl (32 teams), nba (30 teams). NFL/NHL/
   NBA each carry a ``clincher`` stat with a short ``displayValue`` code
   (``x``/``y``/``z``/``xp``/``pb``/``*``/``e``) AND a human-readable
   ``description`` (e.g. "Clinched Playoff Berth", "Eliminated From
   Playoff", "Clinched Presidents' Trophy") -- this module classifies off
   the DESCRIPTION text (substring "clinch"/"eliminat", case-insensitive)
   rather than the terse codes, since the code set already varies by league
   (NBA alone has 7 distinct codes: x/y/z/xp/pb/*/e) and matching on the
   description is robust to that variation without a maintained per-league
   code table. NCAAF (11 conferences, 14ish teams each) and NCAAMB (31
   conferences) return real per-team standings too, but NEITHER carries a
   ``clincher`` stat at all (college football/basketball have no standings-
   based clinch mechanic the way pro leagues do -- playoff access is
   committee/tournament-determined) -- ``parse_standings`` below handles
   this by construction: no ``clincher`` key -> ``PlayoffState()`` defaults
   (clinched=False, eliminated=False, must_win=False), the same fail-closed
   shape as a dead feed, no special-casing needed.

   CAVEAT (build-time, honestly disclosed): this probe ran in July 2026,
   offseason for NFL/NHL/NBA alike (the 2026 NFL season itself doesn't
   start until August per the payload's own ``season.startDate``), yet the
   endpoint returned FULLY-RESOLVED clinch states (17/17 games played,
   final win-loss records) -- almost certainly the just-completed prior
   season's final standings served as the endpoint's off-season default,
   not a genuine in-progress mid-season snapshot. The endpoint's SHAPE is
   therefore verified real and keyless; its accuracy as a genuine "current,
   in-progress season" feed could not be independently confirmed at build
   time (no league was actually in-season to observe). Wiring
   (`TeamSportsIntelligenceSignal.on_cycle_start`) gates every league's
   ``PlayoffBook.refresh()`` behind the SAME ``self.seasons.active(league)``
   check every other per-cycle refresh in this signal already uses, so a
   genuine offseason (like build time) means this book is simply never
   refreshed and stays empty -- zero effect, fail-closed by construction,
   independent of whatever the endpoint happens to return off-season.

2. Transactions/news endpoint (the brief's named fallback trigger for the
   roster-hash-drift proxy): ``https://site.api.espn.com/apis/site/v2/
   sports/{sport}/{league}/transactions`` -- probed nfl/nhl/nba, all 200
   with REAL paginated data (nfl: 844 transactions across 34 pages of 25).
   Each entry is ``{"date", "description": "<free-text>", "team": {...}}``,
   e.g. "Traded WR X to Team Y", "Signed TE ... to a rookie contract",
   "Placed CB ... on injured reserve", "Announced the retirement of ...".
   Contrary to the brief's expectation ("NOT reliably keyless"), this feed
   IS keyless. It is NOT used here anyway: turning free-text transaction
   descriptions into a reliable "significant trade/coaching change"
   classifier (distinguishing a genuine trade from routine practice-squad/
   IR/waiver churn, with correct team attribution and per-cycle pagination
   budgeting across 32+ teams x up to 34 pages) is materially more
   engineering than this workstream's scope -- the brief's own SANCTIONED
   fallback (roster-hash drift via the already-shipped, already-tested
   ``players.default_fetch_roster``) is simpler, bounded, and reuses
   battle-tested WS-6 plumbing verbatim. This is documented here as an
   honest "real but unused" finding, and flagged in ws7-report.md as a
   plausible future upgrade (swap the proxy for the real feed) rather than
   silently ignored.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from autonomy.sports.espn import LEAGUE_TO_ESPN

# =========================================================================
# Shared per-team game-date tracker (generic; see module docstring for why
# NBA's own in-model tracker is deliberately NOT migrated onto this).
# =========================================================================

DEFAULT_DATES_KEPT = 3  # only the most recent date is read by any helper
# below (rest_days_since uses recent_dates[-1]); a couple of spares of
# headroom cost nothing and make a future windowed check (mirroring NBA's
# 3-in-4) cheap to add without a schema change.


def _parse_date(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso[:10])
    except ValueError:
        return None


def rest_days_since(recent_dates: list[str], game_date: str) -> int | None:
    """Days since the most recently tracked game, or None with no history.
    Intentionally identical semantics to (and independent of --see module
    docstring) ``nba_model.py``'s function of the same name."""
    if not recent_dates:
        return None
    last = _parse_date(recent_dates[-1])
    current = _parse_date(game_date)
    if last is None or current is None:
        return None
    return (current - last).days


def _weekday(game_date: str) -> int | None:
    """Python ``date.weekday()``: Monday=0 ... Thursday=3 ... Sunday=6.
    None on an unparseable date (fail-closed -- no weekday-gated adjustment
    fires without a real date)."""
    parsed = _parse_date(game_date)
    return parsed.weekday() if parsed is not None else None


@dataclass
class GameDateTracker:
    """Generic per-league, per-team bounded recent-game-date history,
    learned ONLY from settled games (point-in-time honest, idempotent by
    game_id -- same contract as nba_model.py's ``NbaModel.update``).
    """

    league: str
    teams: dict[str, list[str]] = field(default_factory=dict)
    processed_game_ids: set[str] = field(default_factory=set)
    kept: int = DEFAULT_DATES_KEPT

    def update(self, game: Any) -> bool:
        """Record `game`'s date for both teams iff it is a genuine new
        completed final. Returns False (no-op) on anything else: already
        processed, not yet final, or a missing date -- fail-closed."""
        if game.game_id in self.processed_game_ids or game.status != "post":
            return False
        day = (game.date or "")[:10]
        if not day:
            return False
        for team in (game.home, game.away):
            key = str(team).upper()
            self.teams[key] = (self.teams.get(key, []) + [day])[-self.kept:]
        self.processed_game_ids.add(game.game_id)
        return True

    def recent_dates(self, team: str) -> list[str]:
        return self.teams.get(str(team or "").upper(), [])

    # -- persistence (mirrors nba_model.py::NbaModel.to_dict/save/load) -----

    def to_dict(self) -> dict[str, Any]:
        return {
            "league": self.league,
            "teams": self.teams,
            "processed_game_ids": sorted(self.processed_game_ids),
            "kept": self.kept,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameDateTracker":
        return cls(
            league=str(data.get("league") or ""),
            teams={k: list(v) for k, v in (data.get("teams") or {}).items()},
            processed_game_ids=set(data.get("processed_game_ids", [])),
            kept=int(data.get("kept", DEFAULT_DATES_KEPT)),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path, league: str) -> "GameDateTracker":
        if path.exists():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                pass
        return cls(league=league)


# =========================================================================
# HARD rest states: bounded mean adjust, per-league constants (brief's exact
# values -- candidates for the propose-then-promote tuner, not independently
# fit here, same framing as nba_model.py's own rest constants).
# =========================================================================

NFL_BYE_ADJUSTMENT = 1.0
NFL_BYE_MIN_DAYS = 12          # a normal week's gap is ~6-7 days; a bye
                                # stretches that to ~13-14 -- 12 is a safe
                                # floor that never fires on a normal week.
NFL_SHORT_WEEK_ADJUSTMENT = -1.5
NFL_SHORT_WEEK_MAX_DAYS = 5    # a Thu-after-Sun game is 4 days' rest.
THURSDAY_WEEKDAY = 3           # date.weekday(): Thursday.

NHL_B2B_ADJUSTMENT = -0.8      # goalie-backup proxy (brief's exact framing)

# Encoded constants table, exactly as specced -- also readable programmatically
# by the miner/report tooling rather than re-deriving from the functions below.
REST_CONSTANTS: dict[str, dict[str, float]] = {
    "nfl": {
        "bye": NFL_BYE_ADJUSTMENT,
        "bye_min_days": NFL_BYE_MIN_DAYS,
        "thursday_short_week_road_only": NFL_SHORT_WEEK_ADJUSTMENT,
        "short_week_max_days": NFL_SHORT_WEEK_MAX_DAYS,
    },
    "nhl": {
        "back_to_back": NHL_B2B_ADJUSTMENT,
    },
}


@dataclass(frozen=True)
class RestEffect:
    margin_delta: float = 0.0  # home-minus-away points; 0.0 = no hard effect
    features: dict[str, Any] = field(default_factory=dict)


_EMPTY_REST_EFFECT = RestEffect()


def nfl_team_rest_state(
    recent_dates: list[str], game_date: str, is_home: bool,
) -> tuple[float, dict[str, Any]]:
    """One NFL team's HARD rest-points adjustment (see ``REST_CONSTANTS
    ["nfl"]``):

      * bye: >= ``NFL_BYE_MIN_DAYS`` since the last tracked game ->
        +``NFL_BYE_ADJUSTMENT``, EITHER side.
      * Thursday short week: the game falls on a Thursday AND rest_days <=
        ``NFL_SHORT_WEEK_MAX_DAYS`` -> ``NFL_SHORT_WEEK_ADJUSTMENT``, ROAD
        TEAM ONLY -- brief's exact rule: the home team on a short week gets
        NO penalty, full stop, regardless of its own rest_days.

    No tracked history -> a genuine 0.0/no-op (fail-closed)."""
    days = rest_days_since(recent_dates, game_date)
    weekday = _weekday(game_date)
    bye = days is not None and days >= NFL_BYE_MIN_DAYS
    short_week = (
        not is_home
        and weekday == THURSDAY_WEEKDAY
        and days is not None
        and days <= NFL_SHORT_WEEK_MAX_DAYS
    )
    adjustment = 0.0
    if bye:
        adjustment += NFL_BYE_ADJUSTMENT
    if short_week:
        adjustment += NFL_SHORT_WEEK_ADJUSTMENT
    return adjustment, {
        "rest_days": days, "bye": bye, "thursday_short_week": short_week,
    }


def nfl_rest_effect(
    home_recent_dates: list[str], away_recent_dates: list[str], game_date: str,
) -> RestEffect:
    """Combined NFL bye/short-week effect for one matchup. Sign convention
    (matches players.py::availability_effect): margin_delta is added to the
    HOME side of the expected margin -- hurting a team lowers its margin,
    helping it (a bye) raises it."""
    home_adj, home_features = nfl_team_rest_state(home_recent_dates, game_date, is_home=True)
    away_adj, away_features = nfl_team_rest_state(away_recent_dates, game_date, is_home=False)
    margin_delta = home_adj - away_adj
    features = {f"nfl_rest_home_{k}": v for k, v in home_features.items()}
    features.update({f"nfl_rest_away_{k}": v for k, v in away_features.items()})
    features["nfl_rest_margin_delta"] = round(margin_delta, 3)
    return RestEffect(margin_delta=margin_delta, features=features)


def nhl_team_rest_state(recent_dates: list[str], game_date: str) -> tuple[float, dict[str, Any]]:
    """One NHL team's HARD back-to-back adjustment (goalie-backup proxy,
    brief's exact framing): rest_days == 1 -> ``NHL_B2B_ADJUSTMENT``. No
    tracked history -> a genuine 0.0/no-op (fail-closed)."""
    days = rest_days_since(recent_dates, game_date)
    b2b = days == 1
    adjustment = NHL_B2B_ADJUSTMENT if b2b else 0.0
    return adjustment, {"rest_days": days, "b2b": b2b}


def nhl_rest_effect(
    home_recent_dates: list[str], away_recent_dates: list[str], game_date: str,
) -> RestEffect:
    """Combined NHL back-to-back effect for one matchup, same sign
    convention as ``nfl_rest_effect``. CALLER MUST GATE THIS PRE-GAME ONLY
    (see this module's docstring point 6 / sports_intelligence.py's own
    nba_live/nhl_live comment): a live game's scoreboard already reflects
    whatever a tired backup goalie did, so re-applying this on the live
    branch would double-count it."""
    home_adj, home_features = nhl_team_rest_state(home_recent_dates, game_date)
    away_adj, away_features = nhl_team_rest_state(away_recent_dates, game_date)
    margin_delta = home_adj - away_adj
    features = {f"nhl_rest_home_{k}": v for k, v in home_features.items()}
    features.update({f"nhl_rest_away_{k}": v for k, v in away_features.items()})
    features["nhl_rest_margin_delta"] = round(margin_delta, 3)
    return RestEffect(margin_delta=margin_delta, features=features)


# =========================================================================
# SOFT states: widen uncertainty ONLY, mean byte-identical (see module
# docstring -- the #1 correctness property in this file).
# =========================================================================


@dataclass(frozen=True)
class SoftEffect:
    uncertainty_add: float = 0.0
    features: dict[str, Any] = field(default_factory=dict)


_EMPTY_SOFT_EFFECT = SoftEffect()

# -------------------------------------------------------------- playoff context

CLINCH_UNCERTAINTY = 0.05          # brief: "+0.05 both -- widen only"
SEASON_LENGTH_GAMES: dict[str, int] = {"nfl": 17, "nhl": 82, "nba": 82}
LATE_SEASON_GAMES_PLAYED_FRACTION = 0.75
MUST_WIN_GAMES_REMAINING = 3


@dataclass(frozen=True)
class PlayoffState:
    clinched: bool = False
    eliminated: bool = False
    must_win: bool = False
    games_played: int | None = None
    games_remaining: int | None = None


_EMPTY_PLAYOFF_STATE = PlayoffState()


def _stat_value(stats: dict[str, dict[str, Any]], name: str) -> float | None:
    entry = stats.get(name)
    if not entry:
        return None
    try:
        return float(entry.get("value"))
    except (TypeError, ValueError):
        return None


def parse_standings(league: str, payload: dict[str, Any] | None) -> dict[str, PlayoffState]:
    """Team-abbreviation -> ``PlayoffState`` from a real ESPN standings
    payload (see module docstring probe #1 for the exact URL/shape). A
    league with no ``clincher`` stat at all (NCAAF/NCAAMB -- no pro-style
    standings clinch mechanic) resolves every team to the all-False
    default, matching a dead/absent feed's shape exactly -- no special
    casing needed. Malformed/absent payload -> {} (fail-closed)."""
    league = (league or "").lower()
    season_length = SEASON_LENGTH_GAMES.get(league)
    result: dict[str, PlayoffState] = {}
    for child in (payload or {}).get("children", []) or []:
        entries = ((child.get("standings") or {}).get("entries")) or []
        for entry in entries:
            team = ((entry.get("team") or {}).get("abbreviation") or "").upper()
            if not team:
                continue
            stats = {s.get("name"): s for s in entry.get("stats", []) or [] if s.get("name")}
            wins = _stat_value(stats, "wins")
            losses = _stat_value(stats, "losses")
            ties = _stat_value(stats, "ties") or 0.0
            games_behind = _stat_value(stats, "gamesBehind")
            games_played = games_remaining = None
            if wins is not None and losses is not None and season_length:
                games_played = int(wins + losses + ties)
                games_remaining = max(0, season_length - games_played)
            late_season = (
                season_length is not None
                and games_played is not None
                and games_played / season_length >= LATE_SEASON_GAMES_PLAYED_FRACTION
            )
            clinched = eliminated = False
            has_clincher = "clincher" in stats
            if has_clincher and late_season:
                description = str(stats["clincher"].get("description") or "").lower()
                clinched = "clinch" in description
                eliminated = "eliminat" in description
            must_win = (
                has_clincher and late_season and not clinched and not eliminated
                and games_remaining is not None and games_remaining <= MUST_WIN_GAMES_REMAINING
                and games_behind is not None and games_behind <= games_remaining
            )
            result[team] = PlayoffState(
                clinched=clinched, eliminated=eliminated, must_win=must_win,
                games_played=games_played, games_remaining=games_remaining,
            )
    return result


def _espn_standings_url(league: str) -> str:
    # NOTE: deliberately `apis/v2/...`, NOT `apis/site/v2/...` -- see this
    # module's docstring probe #1 for why the latter (what the brief named)
    # is a dead 86-byte stub.
    sport, espn_league = LEAGUE_TO_ESPN[league]
    return f"https://site.api.espn.com/apis/v2/sports/{sport}/{espn_league}/standings"


def default_fetch_standings(league: str) -> dict[str, Any]:
    import httpx

    response = httpx.get(
        _espn_standings_url(league), headers={"User-Agent": "Mozilla/5.0"}, timeout=15,
    )
    response.raise_for_status()
    return response.json()


class PlayoffBook:
    """Per-league playoff-context book, refreshed once per cycle (mirrors
    players.py::LeagueInjuryBook exactly: fail-closed-to-empty on any fetch
    error, never an implicit fetch outside `refresh`)."""

    def __init__(self, league: str, fetch_fn: Callable[[], dict[str, Any]] | None = None) -> None:
        self.league = (league or "").lower()
        self.fetch_fn = fetch_fn or (lambda: default_fetch_standings(self.league))
        self._teams: dict[str, PlayoffState] | None = None

    def refresh(self) -> None:
        try:
            self._teams = parse_standings(self.league, self.fetch_fn())
        except Exception:
            self._teams = {}

    def for_team(self, team_abbreviation: str | None) -> PlayoffState:
        return (self._teams or {}).get(str(team_abbreviation or "").upper(), _EMPTY_PLAYOFF_STATE)


def playoff_soft_effect(home_state: PlayoffState, away_state: PlayoffState) -> SoftEffect:
    """Widen-only: clinched/eliminated (either side) -> +CLINCH_UNCERTAINTY
    each; NEVER touches the mean (motivation direction is narrative, per the
    brief -- deliberately conservative). must_win is logged only, no
    uncertainty contribution of its own (brief: "flag logged for the
    miner")."""
    uncertainty = 0.0
    if home_state.clinched or home_state.eliminated:
        uncertainty += CLINCH_UNCERTAINTY
    if away_state.clinched or away_state.eliminated:
        uncertainty += CLINCH_UNCERTAINTY
    return SoftEffect(uncertainty_add=uncertainty, features={
        "playoff_clinched_home": home_state.clinched,
        "playoff_eliminated_home": home_state.eliminated,
        "playoff_must_win_home": home_state.must_win,
        "playoff_clinched_away": away_state.clinched,
        "playoff_eliminated_away": away_state.eliminated,
        "playoff_must_win_away": away_state.must_win,
    })


# -------------------------------------------------------- trades/coaching (proxy)

ROSTER_EVENT_UNCERTAINTY = 0.04     # brief's exact value, flat per side
# "a LARGE diff mid-season" (brief) -- a single IR/waiver move churns one
# id out of a ~53-90 man roster; this threshold (>=20% of the union of both
# snapshots' ids changed) is deliberately well above that noise floor so
# routine roster moves don't spuriously fire every cycle. Calibration
# target for the propose-then-promote tuner, not independently fit here
# (same framing as this module's rest-points constants).
ROSTER_DRIFT_FRACTION_THRESHOLD = 0.20


def roster_athlete_ids(roster_payload: dict[str, Any] | None) -> set[str]:
    """Athlete-id set from an ESPN roster payload's position-group
    structure (see players.py's module docstring probe #2 for the exact
    shape: ``{"athletes": [{"items": [{"id": ...}, ...]}, ...]}``)."""
    ids: set[str] = set()
    for group in (roster_payload or {}).get("athletes") or []:
        for item in group.get("items") or []:
            athlete_id = item.get("id")
            if athlete_id:
                ids.add(str(athlete_id))
    return ids


def roster_hash(athlete_ids: set[str]) -> str:
    """Stable fingerprint of a roster's athlete-id set (order-independent)."""
    canonical = ",".join(sorted(athlete_ids))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def roster_drift(previous_ids: set[str] | None, current_ids: set[str]) -> bool:
    """True iff the roster changed enough (>= ROSTER_DRIFT_FRACTION_THRESHOLD
    of the union) to flag a mid-season roster/coaching event. ``previous_ids
    is None`` (first cycle, nothing cached yet) -> False, UNCONDITIONALLY --
    brief: "On the FIRST cycle ... there is no drift -> zero effect"."""
    if previous_ids is None or not current_ids:
        return False
    union = previous_ids | current_ids
    if not union:
        return False
    diff = previous_ids.symmetric_difference(current_ids)
    return (len(diff) / len(union)) >= ROSTER_DRIFT_FRACTION_THRESHOLD


class RosterDriftBook:
    """Per-league roster-hash-drift tracker: caches each team's roster
    athlete-id set across cycles (persisted -- see `to_dict`/`load`), and on
    each `refresh` compares the newly-fetched set to the PRIOR cycle's
    cached one. Fetch-budget-capped and try/except-continue per team,
    mirroring players.py::RookieBook exactly (same team-id resolution path:
    `players.default_fetch_teams`/`parse_team_ids`, reused verbatim rather
    than re-implemented here).
    """

    def __init__(
        self,
        league: str,
        fetch_teams: Callable[[str], dict[str, Any]] | None = None,
        fetch_roster: Callable[[str, str], dict[str, Any]] | None = None,
        fetch_budget: int = 8,
        previous_ids: dict[str, list[str]] | None = None,
    ) -> None:
        from autonomy.sports import players as players_module

        self.league = (league or "").lower()
        self.fetch_teams = fetch_teams or players_module.default_fetch_teams
        self.fetch_roster = fetch_roster or players_module.default_fetch_roster
        self.fetch_budget = fetch_budget
        self._team_ids: dict[str, str] | None = None
        # Persisted across cycles/process restarts (see save/load below) --
        # team abbreviation -> sorted athlete-id list from the LAST cycle
        # this book actually fetched that team's roster.
        self.previous_ids: dict[str, list[str]] = previous_ids or {}
        # This cycle's results only, never persisted.
        self._events: dict[str, dict[str, Any]] = {}

    def _ensure_team_ids(self) -> dict[str, str]:
        from autonomy.sports import players as players_module

        if self._team_ids is None:
            try:
                self._team_ids = players_module.parse_team_ids(self.fetch_teams(self.league))
            except Exception:
                self._team_ids = {}
        return self._team_ids

    def refresh(self, team_abbreviations: list[str]) -> None:
        self._events = {}
        team_ids = self._ensure_team_ids()
        fetched = 0
        for abbreviation in team_abbreviations:
            if fetched >= self.fetch_budget:
                break
            team_id = team_ids.get(str(abbreviation).upper())
            if not team_id:
                continue
            fetched += 1
            try:
                roster_payload = self.fetch_roster(self.league, team_id)
            except Exception:
                continue
            current_ids = roster_athlete_ids(roster_payload)
            if not current_ids:
                continue
            key = str(abbreviation).upper()
            had_previous = key in self.previous_ids
            previous = set(self.previous_ids.get(key, [])) if had_previous else None
            drift = roster_drift(previous, current_ids)
            diff_count = len(previous.symmetric_difference(current_ids)) if previous is not None else 0
            self._events[key] = {
                "roster_event": drift,
                "roster_diff_count": diff_count,
                "roster_size": len(current_ids),
            }
            self.previous_ids[key] = sorted(current_ids)

    def event_for(self, team_abbreviation: str | None) -> dict[str, Any]:
        return self._events.get(
            str(team_abbreviation or "").upper(),
            {"roster_event": False, "roster_diff_count": 0, "roster_size": None},
        )

    # -- persistence ----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {"league": self.league, "previous_ids": self.previous_ids}

    @classmethod
    def from_dict(cls, data: dict[str, Any], **kwargs: Any) -> "RosterDriftBook":
        return cls(
            league=str(data.get("league") or kwargs.pop("league", "")),
            previous_ids={k: list(v) for k, v in (data.get("previous_ids") or {}).items()},
            **kwargs,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path, league: str, **kwargs: Any) -> "RosterDriftBook":
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return cls.from_dict(data, **kwargs)
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                pass
        return cls(league=league, **kwargs)


def roster_soft_effect(home_event: dict[str, Any], away_event: dict[str, Any]) -> SoftEffect:
    """Widen-only: a large roster diff on either side -> +ROSTER_EVENT_
    UNCERTAINTY each; NEVER a mean shift (brief: "NEVER a mean shift")."""
    uncertainty = 0.0
    if home_event.get("roster_event"):
        uncertainty += ROSTER_EVENT_UNCERTAINTY
    if away_event.get("roster_event"):
        uncertainty += ROSTER_EVENT_UNCERTAINTY
    return SoftEffect(uncertainty_add=uncertainty, features={
        "roster_event_home": bool(home_event.get("roster_event")),
        "roster_event_away": bool(away_event.get("roster_event")),
        "roster_diff_count_home": home_event.get("roster_diff_count"),
        "roster_diff_count_away": away_event.get("roster_diff_count"),
    })
