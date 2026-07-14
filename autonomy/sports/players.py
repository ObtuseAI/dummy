"""WS-6: player availability / rookie / mismatch layer, all sports engines.

Challenger-only, fail-closed, point-in-time honest -- same discipline as
every other module in this package. Two correctness properties are load-
bearing (a review WILL check both):

  * HARD statuses (Out/Doubtful) are verifiable roster facts -> allowed to
    shift the expected MARGIN (bounded, position-weighted).
  * SOFT statuses (Questionable/Day-To-Day/Probable) and rookie flags are
    genuine uncertainty, not a known direction -> WIDEN UNCERTAINTY ONLY,
    the mean stays byte-identical.

WS-7 ADDITION -- suspensions route through THIS module's existing hard-Out
path, not a second mean-adjust mechanism: this module's own build-time
probe #1 below already observed a "Suspension" status in the real NHL
injuries feed, which ``classify_status`` was (before WS-7) silently
DROPPING -- neither ``HARD_STATUSES`` nor ``SOFT_STATUSES`` contained it, so
a suspended player had zero effect, same as an untracked "Active"/"Injured
Reserve" row. ``classify_status`` now also matches any status whose text
CONTAINS "suspension"/"suspended" (substring, case-insensitive) and routes
it to "hard" -- reusing ``hard_points_for_player``'s existing position-
weighted delta exactly like an Out/Doubtful row, per WS-7's brief ("hard Out
via the EXISTING WS-6 position-impact path"). No new mean-adjust code path
was added; see situations.py's WS-7 module docstring for the full report.

SCOPE DECISION -- injuries.py left untouched: ``autonomy/sports/injuries.py``
is MLB-only and already in production use by ``BaseballIntelligenceSignal``
(shipped, see MEMORY.md's MLB intelligence directive). Rather than
generalize that class in place -- which would require threading a `league`
parameter through a class whose ``questionable_for``/``burden_for`` MLB
callers must keep returning byte-identical numbers -- this module builds an
independent, richer ``LeagueInjuryBook`` here. injuries.py is not imported
or modified by this file at all; MLB's own test suite
(tests/test_autonomy_injuries.py) is untouched and still exercises the
original class directly. See ws6-report.md for the full justification.

BUILD-TIME PROBES (2026-07-13, network confirmed reachable, keyless):

1. Injuries endpoint shape, one GET per league via
   ``https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/injuries``
   (sport/league path from ``autonomy.sports.espn.LEAGUE_TO_ESPN`` -- reused
   verbatim rather than re-declared here):
     - nfl:    200, 32 teams, statuses observed {Active, Questionable, Out,
       Injured Reserve}. athlete.position.abbreviation present (e.g. "QB").
     - nba:    200, 27 teams, statuses {Day-To-Day, Out}.
     - nhl:    200, 28 teams, statuses {Out, Suspension, Injured Reserve}.
       athlete.position.abbreviation present (e.g. "G", "D", "C", "LW", "RW").
     - ncaaf:  200, 23 teams, statuses {Active, Out, Questionable, Probable}.
     - ncaamb: 200, but ``injuries: []`` (offseason/summer -- empty, not a
       404). Fail-closed handles this identically to a 404: an empty/absent
       book means zero effect either way.
     - mlb:    200, 30 teams (unchanged; injuries.py already covers this).
   Schema is IDENTICAL across every league that returned data: top-level
   ``injuries: [{displayName, injuries: [{status, athlete: {position:
   {abbreviation}, displayName, ...}}]}]``. No 404s observed for any of the
   six leagues at probe time; ncaamb's summer emptiness is the "thin data"
   case the brief anticipated for college feeds.

2. Roster rookie probe -- fetched a real NFL team roster
   (``.../football/nfl/teams/22/roster``): ``athletes`` is a list of
   POSITION-GROUP buckets (``{"position": "offense"|"defense"|
   "specialTeam"|"injuredReserveOrOut"|"suspended", "items": [...]}``), each
   item carrying ``experience.years`` (0 for a confirmed rookie) and
   ``position.abbreviation``. Also fetched an NHL roster
   (``.../hockey/nhl/teams/1/roster``): groups are named
   ``{"Centers","Left Wings","Right Wings","Defense","Goalies"}``.
   CAVEAT (documented, not swept under the rug): ESPN's roster ``items``
   order is NOT a published/guaranteed depth chart -- it is best-effort
   only. This module therefore only ever uses a rookie probe to WIDEN
   uncertainty (+0.04), never to shift a mean, precisely because the signal
   itself is not fully trustworthy. NHL's starting-goalie rookie flag is
   OUT OF SCOPE here: WS-3 already ships a self-derived
   ``rookie_goalie_home/away`` (see nhl_model.py's ``is_rookie_goalie``,
   "goalie handled in WS-3" per the brief) -- this module does not
   duplicate it.
   Also confirmed the team-id resolver this probe needs: the ESPN teams-
   list endpoint (``.../{sport}/{league}/teams``) carries
   ``sports[0].leagues[0].teams[].team.{id,abbreviation,displayName}`` --
   ``abbreviation`` matches the same abbreviations ``autonomy.sports.espn``
   already uses for ``game.home``/``game.away``.

3. Mismatch inputs: reused already-shipped per-team fields rather than
   inventing new stat plumbing -- NBA/NCAAMB rest gap from
   ``NbaPrediction.rest_adjustment_home/away`` (WS-2/WS-4), NHL special-
   teams gap from ``NhlPrediction.special_teams_shift_home/away`` (WS-3).
   NFL/NCAAF have no per-team split metric wired into
   ``TeamSportsIntelligenceSignal`` (no BoxscoreStore instance exists for
   either league there -- only nba/nhl/ncaamb get one); rather than stand
   up a new NFL boxscore-warmup pipeline (real scope creep beyond this
   workstream), NFL/NCAAF mismatch resolves to unavailable/0.0, logged via
   ``{league}_mismatch_unavailable=true`` -- fail-closed, same resolution
   pattern the brief itself sanctions for the NBA-minutes and rookie-proxy
   cases below.

UNSOURCEABLE SUB-FEATURES (brief-sanctioned fail-closed resolutions):
  * NBA "scaled x2 when our own store shows top-2 team minutes": WS-1's
    BoxscoreStore is TEAM-level only, no per-player minutes exist anywhere
    in this codebase. Resolved: default NBA Out weight (-1.8), NO x2
    scaling, ``nba_minutes_scaling_unavailable=true`` logged.
  * Rookie "self-derived proxy: first-N-appearances (<5 games) in our own
    team-level stores": explicitly rejected by this workstream's own
    interface notes ("otherwise set no rookie flag rather than a bogus
    team-level proxy") -- a team's own game count is not a per-player
    signal at all. Not implemented; no flag is set from this path.
  * NFL/NCAAF mismatch score: see probe #3 above.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

from autonomy.sports.espn import LEAGUE_TO_ESPN

# =========================================================================
# Status classification (hard vs soft -- the single most important split)
# =========================================================================

HARD_STATUSES = {"out", "doubtful"}
SOFT_STATUSES = {"questionable", "day-to-day", "probable", "game-time-decision"}

SOFT_UNCERTAINTY_PER_STATUS = 0.02
SOFT_UNCERTAINTY_CAP = 0.08          # per team; brief: "+0.02 each capped +0.08"
ROOKIE_UNCERTAINTY = 0.04            # flat, per confirmed rookie start, never mean


def _status_key(status: Any) -> str:
    return str(status or "").strip().lower()


def classify_status(status: Any) -> str | None:
    """"hard" | "soft" | None (untracked status, e.g. Active/Injured Reserve
    -- long-term/non-doubt statuses are deliberately excluded, same
    reasoning as injuries.py's long-term-IL exclusion).

    WS-7: a status whose text CONTAINS "suspension" (e.g. NHL's observed
    "Suspension" -- see players.py's own build-time probe #1 in this
    module's docstring: {Out, Suspension, Injured Reserve}) is routed to
    "hard" -- a suspension is exactly as verifiable/certain as an Out, and
    the brief directs it through this EXISTING hard-Out position-impact
    path rather than a second mean-adjust mechanism. Checked via substring
    (not exact match) before the HARD_STATUSES/SOFT_STATUSES set lookups so
    a league-specific phrasing variant (e.g. "Suspended") still classifies
    correctly; this never changes any status already in either set below.
    """
    key = _status_key(status)
    if "suspension" in key or "suspended" in key:
        return "hard"
    if key in HARD_STATUSES:
        return "hard"
    if key in SOFT_STATUSES:
        return "soft"
    return None


def _norm_team(text: str | None) -> str:
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


# =========================================================================
# POSITION_IMPACT: hard-availability point deltas (bounded, per brief)
# =========================================================================
# All values are NEGATIVE points subtracted from the affected team's side of
# the expected margin. NHL goalies are intentionally absent (handled by
# WS-3's own goalie_delta_home/away -- see module docstring probe #2).
POSITION_IMPACT: dict[str, dict[str, float]] = {
    "nfl": {"QB": -4.5, "RB_WR": -0.7, "OL": -0.5},
    "nba": {"DEFAULT": -1.8},
    "nhl": {"SKATER": -0.3},
    "ncaaf": {"QB": -2.25, "RB_WR": -0.35, "OL": -0.25},   # half of NFL
    "ncaamb": {"DEFAULT": -0.9},                            # half of NBA
}

# Raw ESPN position.abbreviation -> our position-group key, football leagues.
_FOOTBALL_POSITION_GROUPS: dict[str, str] = {
    "QB": "QB",
    "RB": "RB_WR", "WR": "RB_WR", "TE": "RB_WR", "FB": "RB_WR",
    "OT": "OL", "OG": "OL", "G": "OL", "C": "OL", "T": "OL",
}
# NHL skater positions (goalie "G" is excluded on purpose -- see above).
_NHL_SKATER_POSITIONS = {"C", "LW", "RW", "D"}

# league_point_scale: points-per-"sigma" used to convert a bounded margin/
# mismatch delta into a probability nudge for engines that don't expose a
# raw-score-input kernel (NBA/NHL/NCAAMB -- see shift_probability_by_margin
# below). Mirrors autonomy/sports/team_scores.py's LEAGUE_SCORE_CONFIGS
# margin_sigma values exactly (duplicated here, not imported, so this
# module's tests stay independent of that module's internals) -- NFL/NCAAF
# don't need this table for HARD shifts (they get an EXACT kernel-native
# shift instead, see sports_intelligence.py), but it still doubles as their
# mismatch-margin-shift scale.
LEAGUE_POINT_SCALE: dict[str, float] = {
    "nba": 12.0,
    "ncaamb": 11.0,
    "nfl": 10.0,
    "ncaaf": 14.0,
    "nhl": 2.0,
}

# Source-domain scales for ``bounded_mismatch_score``.  These are NOT point
# spreads: NBA/NCAAMB feed rest-adjustment points capped around +/-2, while
# NHL feeds special-team goal shifts capped at +/-0.15 per side.  The old
# implementation divided those already-bounded inputs by the much larger
# final-score ``LEAGUE_POINT_SCALE`` (12/11/2), making |tanh(.)| > 0.5
# mathematically unreachable in normal operation and leaving the mismatch
# challenger inert.  Keep the input normalization in its native domain; only
# ``mismatch_margin_shift`` converts a fired score into league points/goals.
MISMATCH_INPUT_SCALE: dict[str, float] = {
    "nba": 2.0,
    "ncaamb": 2.0,
    "nhl": 0.25,
}

# Defensive cap on total hard-margin points per team (2x the league's own QB/
# DEFAULT weight) so a pathologically injury-riddled payload can't produce an
# unbounded mean shift. Never binds on the single-QB key test.
_HARD_CAP_MULTIPLE = 2.0


def hard_points_for_player(league: str, position_abbr: str | None) -> float:
    """Position-weighted HARD points for one Out/Doubtful player; 0.0 for an
    unmapped/unknown position (fail-closed: no weight, no effect)."""
    league = (league or "").lower()
    table = POSITION_IMPACT.get(league)
    if table is None:
        return 0.0
    if league in ("nfl", "ncaaf"):
        group = _FOOTBALL_POSITION_GROUPS.get(str(position_abbr or "").upper())
        return table.get(group, 0.0) if group else 0.0
    if league in ("nba", "ncaamb"):
        return table.get("DEFAULT", 0.0)
    if league == "nhl":
        pos = str(position_abbr or "").upper()
        if pos == "G":
            return 0.0  # goalies: WS-3's own layer, not this module's
        if pos in _NHL_SKATER_POSITIONS:
            return table.get("SKATER", 0.0)
        return 0.0
    return 0.0


# =========================================================================
# Injuries: parse + book (independent of injuries.py -- see module docstring)
# =========================================================================


@dataclass(frozen=True)
class TeamAvailability:
    hard_points: float = 0.0           # signed, <= 0; bounded per _HARD_CAP_MULTIPLE
    soft_count: int = 0                # count of Questionable/DTD/Probable entries
    hard_labels: tuple[str, ...] = ()  # e.g. ("QB:Out",) -- for feature logging


_EMPTY_AVAILABILITY = TeamAvailability()


def parse_team_availability(league: str, payload: dict[str, Any] | None) -> dict[str, TeamAvailability]:
    """Normalized-team-name -> TeamAvailability. [] / malformed payload ->
    {} (fail-closed, mirrors injuries.py's parse_team_injuries contract)."""
    league = (league or "").lower()
    result: dict[str, TeamAvailability] = {}
    cap = abs(
        POSITION_IMPACT.get(league, {}).get("QB")
        or POSITION_IMPACT.get(league, {}).get("DEFAULT")
        or 4.5
    ) * _HARD_CAP_MULTIPLE
    for team in (payload or {}).get("injuries", []) or []:
        name = _norm_team(team.get("displayName"))
        if not name:
            continue
        hard_points = 0.0
        hard_labels: list[str] = []
        soft_count = 0
        for injury in team.get("injuries", []) or []:
            cls = classify_status(injury.get("status"))
            if cls is None:
                continue
            if cls == "soft":
                soft_count += 1
                continue
            position = ((injury.get("athlete") or {}).get("position") or {}).get("abbreviation")
            points = hard_points_for_player(league, position)
            if points != 0.0:
                hard_points += points
                hard_labels.append(f"{position or '?'}:{injury.get('status')}")
        hard_points = max(-cap, hard_points)
        result[name] = TeamAvailability(
            hard_points=hard_points, soft_count=soft_count, hard_labels=tuple(hard_labels),
        )
    return result


def _espn_injuries_url(league: str) -> str:
    sport, espn_league = LEAGUE_TO_ESPN[league]
    return f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{espn_league}/injuries"


def default_fetch_league_injuries(league: str) -> dict[str, Any]:
    """Fetch the ESPN league injuries payload (keyless, read-only)."""
    import httpx

    response = httpx.get(
        _espn_injuries_url(league), headers={"User-Agent": "Mozilla/5.0"}, timeout=15,
    )
    response.raise_for_status()
    return response.json()


class LeagueInjuryBook:
    """Per-league HARD/SOFT availability book. Independent of
    ``autonomy/sports/injuries.py``'s MLB-only ``InjuryBook`` -- see this
    module's docstring for why. Same refresh-once-per-cycle,
    fail-closed-to-empty discipline.
    """

    def __init__(self, league: str, fetch_fn: Callable[[], dict[str, Any]] | None = None) -> None:
        self.league = (league or "").lower()
        self.fetch_fn = fetch_fn or (lambda: default_fetch_league_injuries(self.league))
        self._teams: dict[str, TeamAvailability] | None = None

    def refresh(self) -> None:
        try:
            self._teams = parse_team_availability(self.league, self.fetch_fn())
        except Exception:
            self._teams = {}

    def _ensure(self) -> dict[str, TeamAvailability]:
        return self._teams or {}

    def for_team(self, team_name: str | None) -> TeamAvailability:
        return self._ensure().get(_norm_team(team_name), _EMPTY_AVAILABILITY)


# =========================================================================
# Rookie start (NFL QB only -- NHL goalie already shipped by WS-3)
# =========================================================================


def default_fetch_teams(league: str) -> dict[str, Any]:
    import httpx

    sport, espn_league = LEAGUE_TO_ESPN[league]
    response = httpx.get(
        f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{espn_league}/teams",
        headers={"User-Agent": "Mozilla/5.0"}, params={"limit": 100}, timeout=15,
    )
    response.raise_for_status()
    return response.json()


def parse_team_ids(payload: dict[str, Any] | None) -> dict[str, str]:
    """abbreviation (e.g. "KC") -> ESPN numeric team id. [] on malformed
    payload (fail-closed)."""
    result: dict[str, str] = {}
    try:
        leagues = (((payload or {}).get("sports") or [{}])[0].get("leagues") or [{}])[0]
        entries = leagues.get("teams") or []
    except (IndexError, AttributeError, TypeError):
        return {}
    for entry in entries:
        team = entry.get("team") or {}
        abbreviation = team.get("abbreviation")
        team_id = team.get("id")
        if abbreviation and team_id:
            result[str(abbreviation).upper()] = str(team_id)
    return result


def default_fetch_roster(league: str, team_id: str) -> dict[str, Any]:
    import httpx

    sport, espn_league = LEAGUE_TO_ESPN[league]
    response = httpx.get(
        f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{espn_league}/teams/{team_id}/roster",
        headers={"User-Agent": "Mozilla/5.0"}, timeout=15,
    )
    response.raise_for_status()
    return response.json()


def probe_rookie_qb_start(roster_payload: dict[str, Any] | None) -> bool | None:
    """Best-effort NFL QB-rookie probe from a team roster payload: the
    first-listed "offense" group player at QB with experience.years == 0.

    CAVEAT (see module docstring probe #2): ESPN's roster item order is NOT
    a documented depth chart. This is why the flag this feeds is
    uncertainty-only (+0.04), never a mean shift -- the probe itself is
    acknowledged-unreliable. Returns None (no flag) on any missing/
    ambiguous data -- fail closed, per this workstream's own interface
    notes ("otherwise set no rookie flag rather than a bogus proxy").
    """
    groups = (roster_payload or {}).get("athletes") or []
    for group in groups:
        if str(group.get("position") or "").lower() != "offense":
            continue
        items = group.get("items") or []
        qbs = [p for p in items if ((p.get("position") or {}).get("abbreviation") == "QB")]
        if not qbs:
            return None
        years = ((qbs[0].get("experience") or {}).get("years"))
        if years is None:
            return None
        return years == 0
    return None


class RookieBook:
    """NFL QB rookie-start flags, resolved via the roster probe above.
    Fetch-budget-capped and cached per cycle (mirrors the boxscore/
    goalie/neutral-site caches in sports_intelligence.py) -- one teams-list
    fetch (cached for the book's lifetime) plus up to `fetch_budget` roster
    fetches per refresh, never per-market.
    """

    def __init__(
        self,
        league: str,
        fetch_teams: Callable[[str], dict[str, Any]] | None = None,
        fetch_roster: Callable[[str, str], dict[str, Any]] | None = None,
        fetch_budget: int = 8,
    ) -> None:
        self.league = (league or "").lower()
        self.fetch_teams = fetch_teams or default_fetch_teams
        self.fetch_roster = fetch_roster or default_fetch_roster
        self.fetch_budget = fetch_budget
        self._team_ids: dict[str, str] | None = None
        self._flags: dict[str, bool] = {}

    def _ensure_team_ids(self) -> dict[str, str]:
        if self._team_ids is None:
            try:
                self._team_ids = parse_team_ids(self.fetch_teams(self.league))
            except Exception:
                self._team_ids = {}
        return self._team_ids

    def refresh(self, team_abbreviations: list[str]) -> None:
        """Probe up to `fetch_budget` teams from `team_abbreviations` (a
        try/except-continue loop, one bad fetch never blocks the rest --
        same discipline as _warmup_nba/_warmup_nhl)."""
        self._flags = {}
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
                roster = self.fetch_roster(self.league, team_id)
            except Exception:
                continue
            flag = probe_rookie_qb_start(roster)
            if flag is not None:
                self._flags[str(abbreviation).upper()] = flag

    def rookie_start(self, team_abbreviation: str | None) -> bool | None:
        return self._flags.get(str(team_abbreviation or "").upper())


# =========================================================================
# Mismatch finder (bounded, symmetric)
# =========================================================================


def bounded_mismatch_score(home_metric: float, away_metric: float, scale: float) -> float:
    """tanh((home - away) / scale) -- bounded to (-1, 1) by construction,
    and EXACTLY negated by swapping home_metric/away_metric (tanh is odd)."""
    if scale is None or scale <= 0:
        return 0.0
    return math.tanh((float(home_metric) - float(away_metric)) / float(scale))


def mismatch_margin_shift(score: float, league_point_scale: float) -> float:
    """0.0 when |score| <= 0.5; otherwise sign(score) * min(|score|, 1.0) *
    0.3 * league_point_scale -- bounded, and 0 exactly at the |score|==0.5
    boundary (brief: "shifts mean ... ONLY when |score| > 0.5")."""
    magnitude = min(abs(score), 1.0)
    if magnitude <= 0.5:
        return 0.0
    sign = 1.0 if score > 0 else -1.0
    return sign * magnitude * 0.3 * float(league_point_scale)


# =========================================================================
# Probability shift for engines with no raw-score-input kernel
# (NBA/NHL/NCAAMB -- NFL/NCAAF instead inject the shift into their margin
# kernel's input scores directly in sports_intelligence.py, for an EXACT
# margin shift rather than this approximation.)
# =========================================================================


def shift_probability_by_margin(
    probability: float, delta_margin: float, point_scale: float, subject_is_home: bool,
) -> float:
    """Nudge a probability by a points-denominated margin delta via a
    logit-space shift (bounded to (0,1) automatically, monotonic, and an
    EXACT no-op at delta_margin == 0.0 -- no float round-trip through
    log/exp on the zero-effect path, which the fail-closed byte-identical
    test depends on).
    """
    if delta_margin == 0.0 or not point_scale or point_scale <= 0:
        return probability
    effective = delta_margin if subject_is_home else -delta_margin
    p = min(0.995, max(0.005, float(probability)))
    logit = math.log(p / (1.0 - p))
    new_logit = logit + effective / float(point_scale)
    shifted = 1.0 / (1.0 + math.exp(-new_logit))
    return min(0.995, max(0.005, shifted))


def apply_margin_shift_to_scores(
    expected_home_score: float, expected_away_score: float, delta_margin: float,
) -> tuple[float, float]:
    """Split `delta_margin` symmetrically across both sides so the resulting
    (home - away) margin shifts by EXACTLY delta_margin while the total
    (home + away) is preserved -- used to feed NFL/NCAAF's margin kernel an
    availability-adjusted matchup without perturbing the total-points line.
    """
    half = delta_margin / 2.0
    return expected_home_score + half, expected_away_score - half


# =========================================================================
# Availability aggregate: HARD margin delta + SOFT/rookie uncertainty
# =========================================================================


@dataclass(frozen=True)
class AvailabilityEffect:
    hard_margin_delta: float = 0.0   # home-minus-away points; 0.0 = no hard effect
    soft_uncertainty_add: float = 0.0
    rookie_uncertainty_add: float = 0.0
    features: dict[str, Any] = field(default_factory=dict)


def availability_effect(
    league: str,
    home_availability: TeamAvailability,
    away_availability: TeamAvailability,
    home_rookie_start: bool | None = None,
    away_rookie_start: bool | None = None,
) -> AvailabilityEffect:
    """Combine one game's HARD/SOFT injury + rookie signals into a single
    bounded effect, with every input logged for the miner to grade later.

    Sign convention: hard_margin_delta is added to the HOME side of the
    expected margin (a negative value lowers the home margin -- "hurting the
    home team lowers home margin", per the brief). home_availability's own
    hard_points is already negative (a penalty against home's side), and
    away_availability's hard_points must flip sign (a penalty against away
    is a positive contribution to home's relative margin).
    """
    hard_margin_delta = home_availability.hard_points - away_availability.hard_points
    soft_uncertainty_add = min(
        SOFT_UNCERTAINTY_CAP, SOFT_UNCERTAINTY_PER_STATUS * home_availability.soft_count,
    ) + min(
        SOFT_UNCERTAINTY_CAP, SOFT_UNCERTAINTY_PER_STATUS * away_availability.soft_count,
    )
    rookie_uncertainty_add = ROOKIE_UNCERTAINTY * (
        int(bool(home_rookie_start)) + int(bool(away_rookie_start))
    )
    return AvailabilityEffect(
        hard_margin_delta=hard_margin_delta,
        soft_uncertainty_add=soft_uncertainty_add,
        rookie_uncertainty_add=rookie_uncertainty_add,
        features={
            "hard_margin_delta": round(hard_margin_delta, 3),
            "hard_labels_home": list(home_availability.hard_labels),
            "hard_labels_away": list(away_availability.hard_labels),
            "soft_count_home": home_availability.soft_count,
            "soft_count_away": away_availability.soft_count,
            "soft_uncertainty_add": round(soft_uncertainty_add, 4),
            "rookie_start_home": home_rookie_start,
            "rookie_start_away": away_rookie_start,
            "rookie_uncertainty_add": round(rookie_uncertainty_add, 4),
        },
    )
