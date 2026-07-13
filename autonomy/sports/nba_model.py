"""NBA pace x efficiency model: heteroskedastic, rest-aware, live-diffusion.

Point-in-time challenger (spec Sec.5.2 / WS-2). Learns two per-team EWMA
efficiency numbers -- offensive rating (points scored per 100 possessions)
and defensive rating (points allowed per 100 possessions) -- plus a shared
pace (possessions/game) EWMA, all sourced from WS-1's boxscore-derived
possession estimate (autonomy/sports/boxscores.py) combined with the
scoreboard's own final score (NBA `points` is NOT present in the boxscore
statistics rows -- see that module's WS-1 report -- so this model reads
scores from `Game.home_score`/`away_score`, exactly like every other engine
in this package).

Matchup expected scores come from pace x efficiency (`expected_pace *
eff_home/100`); dispersion around them is HETEROSKEDASTIC -- both sigmas
scale with sqrt(expected_pace/99.5), so a fast, possession-rich matchup is
correctly modeled as higher-variance than a slow, grinding one (unlike the
generic TeamScoreModel's fixed sigma). Winner and every spread rung price
off the SAME normal (Phi(margin/margin_sigma)), so the winner cell and the
spread ladder are coherent by construction, mirroring
autonomy/sports/nfl_margin.py's single-distribution discipline.

A bounded rest engine (back-to-back / 3-in-4 / rest advantage; see the
constants table below) nudges the mean. A garbage-time cap keeps blowouts
from teaching the ORTG/DRTG EWMAs a false read on true team strength.

Below MIN_GAMES_FOR_ENGINE boxscore-observed games for either team, the
signal integration (autonomy/signals/sports_intelligence.py) falls back to
the generic autonomy/sports/team_scores.py::TeamScoreModel prediction
WHOLESALE -- never a half-blend -- exactly like a cold NFL matchup falls
back from autonomy/sports/nfl_margin.py::NflMarginModel to the same generic
model.

In-play markets price off a Brownian-bridge approximation of the remaining
game (see the live_* functions), gated exactly like MLB's live branch
(`game.status == "in"` with a valid period) in autonomy/sports/baseball.py.

PROBE (build-time, 2026-07-12, network confirmed reachable): fetched the NBA
scoreboard for an in-season date --
``https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20260401``
-- and located event 401810960 (PHI @ WSH, 2026-04-01; the same completed
game WS-1's boxscore probe used). Its `competitions[0].status` block:

    {
      "clock": 0.0,
      "displayClock": "0.0",
      "period": 4,
      "type": {"id": "3", "name": "STATUS_FINAL", "state": "post", ...}
    }

confirms the exact field names this module's live branch depends on:
`status.period` (int, quarter number; already parsed by
autonomy/sports/espn.py::parse_scoreboard into `Game.current_period`, gated
to `state == "in"`) and `status.displayClock` (string; parsed here into
`Game.current_clock`, same gate). NBA is OFFSEASON in July, so no genuinely
`"in"`-state game could be observed at build time to confirm the live
"MM:SS" shape directly -- only this completed game's terminal "0.0" value
was observable. `minutes_remaining_in_game`/`parse_clock_minutes` below are
therefore fail-closed on any string that doesn't match "M:SS": an
unexpected live format degrades to None (the live branch abstains) rather
than mis-parsing silently. The `status.clock` numeric-seconds field is
recorded here for completeness but unused -- `displayClock` is the field the
brief named and is sufficient once parsed.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from autonomy.sports.boxscores import BoxscoreStore, TeamBoxscore
from autonomy.sports.espn import Game

MODEL_VERSION = "nba_pace_efficiency_v1"

# -- cold priors + reliability weighting (mirrors team_scores.py::_metric) --
PRIOR_PACE = 99.5            # league-average possessions/game
PRIOR_RATING = 114.0         # league-average pts/100 poss (ORTG == DRTG prior)
EWMA_ALPHA = 0.10
COLD_FULL_WEIGHT_GAMES = 25.0   # reliability weight = min(COLD_WEIGHT_CAP, games/25)
COLD_WEIGHT_CAP = 0.85

# -- matchup ------------------------------------------------------------------
HOME_EDGE_POINTS = 3.0
# Sanity floor only (never observed in practice) -- keeps the normal well
# defined at absurd cold-start/extreme-adjustment inputs, not a modeling
# boundary (mirrors the analogous floors in team_scores.py/baseball.py).
MIN_SANE_TEAM_SCORE = 60.0

# -- heteroskedastic sigmas: calibration targets for the propose-then-promote
# tuner, not independently fit here (mirrors nfl_margin.py's own framing of
# its constants). Both scale with sqrt(expected_pace / SIGMA_PACE_REFERENCE).
TOTAL_SIGMA_BASE = 19.5
MARGIN_SIGMA_BASE = 11.5
SIGMA_PACE_REFERENCE = 99.5

# -- garbage time --------------------------------------------------------------
# Blowout tails lie about true team strength; cap the margin BEFORE it
# teaches the ORTG/DRTG EWMAs anything past this.
GARBAGE_TIME_MARGIN_CAP = 25.0

# -- rest engine: HARD, bounded states (brief's exact point values, not
# independently fit -- candidates for the propose-then-promote tuner like
# the sigma constants above). ------------------------------------------------
B2B_ADJUSTMENT = -1.5           # back-to-back: rest_days == 1
THREE_IN_FOUR_ADJUSTMENT = -1.0  # 3rd+ game within a trailing 4-day window
REST_BONUS = 0.5                 # >= 3 days since the last game
REST_STACK_CAP = -2.0            # b2b + 3-in-4 can co-occur; floor the sum here
THREE_IN_FOUR_WINDOW_DAYS = 4
THREE_IN_FOUR_GAME_COUNT = 3     # >= this many games (incl. today) in the window
REST_BONUS_DAYS = 3
# Bounded per-team date history: a single "last game date" can only ever
# test b2b. 3-in-4 needs a trailing window, so this keeps a short, capped
# list instead (still O(1) state, never unbounded growth) -- 4 entries is
# exactly enough to evaluate a 4-day window without keeping full history.
RECENT_DATES_KEPT = 4

# -- fallback threshold ---------------------------------------------------------
MIN_GAMES_FOR_ENGINE = 5   # below this in WS-1's BoxscoreStore for EITHER team -> fall back wholesale

# -- live Brownian diffusion -----------------------------------------------------
REGULATION_MINUTES = 48.0
MINUTES_PER_QUARTER = 12.0


# =============================================================== pace math


def possessions(fga: float, orb: float, to: float, fta: float) -> float:
    """WS-1's possession estimate: FGA - ORB + TO + 0.44*FTA."""
    return fga - orb + to + 0.44 * fta


def game_pace(home_box: TeamBoxscore, away_box: TeamBoxscore) -> float | None:
    """One game's pace: the average of both teams' own-boxscore possession
    estimates (they play ~the same number of possessions up to end-of-period
    no-shot variance). Fail-closed: a missing WS-1 stat key -> None.
    """
    try:
        home_poss = possessions(
            home_box.stats["fieldGoalsAttempted"], home_box.stats["offensiveRebounds"],
            home_box.stats["turnovers"], home_box.stats["freeThrowsAttempted"],
        )
        away_poss = possessions(
            away_box.stats["fieldGoalsAttempted"], away_box.stats["offensiveRebounds"],
            away_box.stats["turnovers"], away_box.stats["freeThrowsAttempted"],
        )
    except KeyError:
        return None
    return (home_poss + away_poss) / 2.0


def clamp_margin(home_score: float, away_score: float) -> tuple[float, float]:
    """Garbage-time cap: (effective_home, effective_away) with the final
    margin clamped to +/-GARBAGE_TIME_MARGIN_CAP, total held constant.
    """
    margin = float(home_score) - float(away_score)
    if margin == 0.0:
        capped = 0.0
    else:
        capped = math.copysign(min(abs(margin), GARBAGE_TIME_MARGIN_CAP), margin)
    total = float(home_score) + float(away_score)
    return (total + capped) / 2.0, (total - capped) / 2.0


# ======================================================= distribution math


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def heteroskedastic_sigmas(expected_pace: float) -> tuple[float, float]:
    """(total_sigma, margin_sigma) for a matchup at this expected pace."""
    ratio = math.sqrt(max(0.0, float(expected_pace)) / SIGMA_PACE_REFERENCE)
    return TOTAL_SIGMA_BASE * ratio, MARGIN_SIGMA_BASE * ratio


def win_probability_from_margin(margin: float, margin_sigma: float) -> float:
    z = margin / max(0.25, margin_sigma)
    return min(0.995, max(0.005, normal_cdf(z)))


def spread_cover_probability(margin: float, margin_sigma: float, threshold: float) -> float:
    """P(margin > threshold) via the SAME normal that prices the winner cell
    (threshold=0.0 reduces exactly to `win_probability_from_margin`)."""
    z = (margin - threshold) / max(0.25, margin_sigma)
    return min(0.995, max(0.005, normal_cdf(z)))


def total_over_probability(expected_total: float, total_sigma: float, threshold: float) -> float:
    z = (expected_total - threshold) / max(0.25, total_sigma)
    return min(0.995, max(0.005, normal_cdf(z)))


# ============================================================== rest engine


def _parse_date(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso[:10])
    except ValueError:
        return None


def rest_days_since(recent_dates: list[str], game_date: str) -> int | None:
    """Days since the most recent tracked game, or None with no history."""
    if not recent_dates:
        return None
    last = _parse_date(recent_dates[-1])
    current = _parse_date(game_date)
    if last is None or current is None:
        return None
    return (current - last).days


def _games_within_window(recent_dates: list[str], game_date: str, window_days: int) -> int:
    current = _parse_date(game_date)
    if current is None:
        return 0
    count = 1  # the upcoming game itself
    for iso in recent_dates:
        played = _parse_date(iso)
        if played is not None and 0 < (current - played).days < window_days:
            count += 1
    return count


def rest_adjustment(recent_dates: list[str], game_date: str) -> tuple[float, int | None]:
    """(points adjustment, rest_days) for one team ahead of `game_date`.

    HARD, bounded rest engine (brief's exact constants -- see the table
    above): b2b and 3-in-4 can co-occur and stack (capped at
    REST_STACK_CAP); the rest bonus is mutually exclusive with both by
    definition (rest_days can't simultaneously be 1 and >= 3). No history ->
    a genuine 0.0/None no-op.
    """
    days = rest_days_since(recent_dates, game_date)
    if days is None:
        return 0.0, None
    adjustment = 0.0
    if days == 1:
        adjustment += B2B_ADJUSTMENT
    if _games_within_window(recent_dates, game_date, THREE_IN_FOUR_WINDOW_DAYS) >= THREE_IN_FOUR_GAME_COUNT:
        adjustment += THREE_IN_FOUR_ADJUSTMENT
    adjustment = max(REST_STACK_CAP, adjustment)
    if days >= REST_BONUS_DAYS:
        adjustment += REST_BONUS
    return adjustment, days


# ======================================================= live clock parsing


def parse_clock_minutes(display_clock: str | None) -> float | None:
    """ESPN "status.displayClock" ("M:SS" / "MM:SS") -> minutes remaining IN
    THE CURRENT PERIOD. Fail-closed: anything else (e.g. the terminal "0.0"
    a completed game shows) -> None.
    """
    if not display_clock:
        return None
    match = re.match(r"^(\d+):(\d{2})$", display_clock.strip())
    if not match:
        return None
    minutes, seconds = int(match.group(1)), int(match.group(2))
    return minutes + seconds / 60.0


def minutes_remaining_in_game(period: int | None, display_clock: str | None) -> float | None:
    """Total regulation-basis minutes left, given the current period (1-4)
    and that period's display clock. None on any missing/unparseable input
    (fail-closed -- the live branch simply abstains).

    OT (period >= 5): only the current extra period's own clock counts --
    the model's REGULATION_MINUTES=48 sigma_live basis is a regulation
    approximation (see module docstring); extending it into overtime isn't
    attempted here.
    """
    if period is None or period < 1:
        return None
    clock_minutes = parse_clock_minutes(display_clock)
    if clock_minutes is None:
        return None
    if period <= 4:
        remaining_full_quarters = 4 - period
        return remaining_full_quarters * MINUTES_PER_QUARTER + clock_minutes
    return clock_minutes


# ========================================================= live Brownian


def live_sigma(margin_sigma: float) -> float:
    return margin_sigma / math.sqrt(REGULATION_MINUTES)


def live_win_probability(
    lead: float, minutes_remaining: float, margin_sigma: float, expected_margin: float = 0.0,
) -> float:
    """P(home wins | lead L, t_remaining) = Phi((L + drift*t)/(sigma_live*sqrt(t))),
    sigma_live = margin_sigma/sqrt(48), drift = expected_margin/48 per minute.
    """
    t = max(1e-6, float(minutes_remaining))
    sigma_live = live_sigma(margin_sigma)
    drift = expected_margin / REGULATION_MINUTES
    z = (float(lead) + drift * t) / (sigma_live * math.sqrt(t))
    return min(0.9995, max(0.0005, normal_cdf(z)))


def live_spread_probability(
    lead: float, threshold: float, minutes_remaining: float, margin_sigma: float,
    expected_margin: float = 0.0,
) -> float:
    """P(subject margin > threshold | current lead), analogous to
    `live_win_probability` with the strike shifted into the lead."""
    t = max(1e-6, float(minutes_remaining))
    sigma_live = live_sigma(margin_sigma)
    drift = expected_margin / REGULATION_MINUTES
    z = (float(lead) - float(threshold) + drift * t) / (sigma_live * math.sqrt(t))
    return min(0.9995, max(0.0005, normal_cdf(z)))


def live_total_probability(
    current_total: float, threshold: float, minutes_remaining: float,
    total_sigma: float, expected_total: float,
) -> float:
    """P(final total > threshold): points already scored plus a Brownian
    remainder whose mean AND variance are pro-rated by the time left."""
    t = max(1e-6, float(minutes_remaining))
    fraction = t / REGULATION_MINUTES
    remaining_mean = expected_total * fraction
    sigma_remaining = max(0.25, total_sigma * math.sqrt(fraction))
    z = (float(current_total) + remaining_mean - float(threshold)) / sigma_remaining
    return min(0.9995, max(0.0005, normal_cdf(z)))


# =================================================================== state


@dataclass
class NbaTeamState:
    games: int = 0
    pace_ewma: float = PRIOR_PACE
    ortg_ewma: float = PRIOR_RATING
    drtg_ewma: float = PRIOR_RATING
    # Bounded recent-game-date history ("YYYY-MM-DD"), oldest first, capped
    # at RECENT_DATES_KEPT -- see the module-level comment on RECENT_DATES_KEPT.
    recent_dates: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NbaPrediction:
    home_win_probability: float
    expected_home_score: float
    expected_away_score: float
    expected_total: float
    expected_margin: float
    total_sigma: float
    margin_sigma: float
    expected_pace: float
    rest_days_home: int | None
    rest_days_away: int | None
    rest_adjustment_home: float
    rest_adjustment_away: float
    sample_games: int
    model_version: str = MODEL_VERSION


# =============================================================== the model


@dataclass
class NbaModel:
    teams: dict[str, NbaTeamState] = field(default_factory=dict)
    processed_game_ids: set[str] = field(default_factory=set)
    games_seen: int = 0

    def _team(self, abbreviation: str) -> NbaTeamState:
        return self.teams.setdefault(abbreviation.upper(), NbaTeamState())

    def _metric(self, state: NbaTeamState, field_name: str, prior: float) -> float:
        weight = min(COLD_WEIGHT_CAP, state.games / COLD_FULL_WEIGHT_GAMES)
        return (1.0 - weight) * prior + weight * float(getattr(state, field_name))

    def update(
        self, game: Game, home_box: TeamBoxscore | None, away_box: TeamBoxscore | None,
    ) -> bool:
        """Settlement-only learning: refuses anything but a completed final
        with both teams' WS-1 boxscores (point-in-time honesty -- live
        diffusion never enters learning). Idempotent by game_id.
        """
        if (
            game.game_id in self.processed_game_ids
            or game.status != "post"
            or game.home_score is None
            or game.away_score is None
            or home_box is None
            or away_box is None
        ):
            return False
        pace = game_pace(home_box, away_box)
        if pace is None or pace <= 0:
            return False
        home = self._team(game.home)
        away = self._team(game.away)
        effective_home, effective_away = clamp_margin(float(game.home_score), float(game.away_score))
        home.pace_ewma = EWMA_ALPHA * pace + (1.0 - EWMA_ALPHA) * home.pace_ewma
        away.pace_ewma = EWMA_ALPHA * pace + (1.0 - EWMA_ALPHA) * away.pace_ewma
        home_ortg = effective_home / pace * 100.0
        home_drtg = effective_away / pace * 100.0
        away_ortg = effective_away / pace * 100.0
        away_drtg = effective_home / pace * 100.0
        home.ortg_ewma = EWMA_ALPHA * home_ortg + (1.0 - EWMA_ALPHA) * home.ortg_ewma
        home.drtg_ewma = EWMA_ALPHA * home_drtg + (1.0 - EWMA_ALPHA) * home.drtg_ewma
        away.ortg_ewma = EWMA_ALPHA * away_ortg + (1.0 - EWMA_ALPHA) * away.ortg_ewma
        away.drtg_ewma = EWMA_ALPHA * away_drtg + (1.0 - EWMA_ALPHA) * away.drtg_ewma
        game_day = (game.date or "")[:10]
        if game_day:
            home.recent_dates = (home.recent_dates + [game_day])[-RECENT_DATES_KEPT:]
            away.recent_dates = (away.recent_dates + [game_day])[-RECENT_DATES_KEPT:]
        home.games += 1
        away.games += 1
        self.games_seen += 1
        self.processed_game_ids.add(game.game_id)
        return True

    def predict(self, game: Game) -> NbaPrediction:
        home = self._team(game.home)
        away = self._team(game.away)
        pace_home = self._metric(home, "pace_ewma", PRIOR_PACE)
        pace_away = self._metric(away, "pace_ewma", PRIOR_PACE)
        expected_pace = (pace_home + pace_away) / 2.0

        ortg_home = self._metric(home, "ortg_ewma", PRIOR_RATING)
        drtg_home = self._metric(home, "drtg_ewma", PRIOR_RATING)
        ortg_away = self._metric(away, "ortg_ewma", PRIOR_RATING)
        drtg_away = self._metric(away, "drtg_ewma", PRIOR_RATING)
        eff_home = (ortg_home + drtg_away) / 2.0
        eff_away = (ortg_away + drtg_home) / 2.0

        game_day = (game.date or "")[:10]
        if game_day:
            rest_adj_home, rest_days_home = rest_adjustment(home.recent_dates, game_day)
            rest_adj_away, rest_days_away = rest_adjustment(away.recent_dates, game_day)
        else:
            rest_adj_home, rest_days_home = 0.0, None
            rest_adj_away, rest_days_away = 0.0, None

        expected_home = expected_pace * eff_home / 100.0 + HOME_EDGE_POINTS / 2.0 + rest_adj_home
        expected_away = expected_pace * eff_away / 100.0 - HOME_EDGE_POINTS / 2.0 + rest_adj_away
        expected_home = max(MIN_SANE_TEAM_SCORE, expected_home)
        expected_away = max(MIN_SANE_TEAM_SCORE, expected_away)

        total_sigma, margin_sigma = heteroskedastic_sigmas(expected_pace)
        expected_margin = expected_home - expected_away
        sample = min(home.games, away.games)
        return NbaPrediction(
            home_win_probability=win_probability_from_margin(expected_margin, margin_sigma),
            expected_home_score=expected_home,
            expected_away_score=expected_away,
            expected_total=expected_home + expected_away,
            expected_margin=expected_margin,
            total_sigma=total_sigma,
            margin_sigma=margin_sigma,
            expected_pace=expected_pace,
            rest_days_home=rest_days_home,
            rest_days_away=rest_days_away,
            rest_adjustment_home=rest_adj_home,
            rest_adjustment_away=rest_adj_away,
            sample_games=sample,
        )

    # -- pre-game -------------------------------------------------------

    def cover_probability(
        self, prediction: NbaPrediction, subject_is_home: bool, threshold: float,
    ) -> float:
        margin = prediction.expected_margin if subject_is_home else -prediction.expected_margin
        return spread_cover_probability(margin, prediction.margin_sigma, threshold)

    def total_probability(self, prediction: NbaPrediction, threshold: float) -> float:
        return total_over_probability(prediction.expected_total, prediction.total_sigma, threshold)

    # -- live -------------------------------------------------------------

    def live_win_probability_for(
        self, prediction: NbaPrediction, home_score: float, away_score: float,
        minutes_remaining: float,
    ) -> float:
        lead = float(home_score) - float(away_score)
        return live_win_probability(
            lead, minutes_remaining, prediction.margin_sigma, prediction.expected_margin)

    def live_spread_probability_for(
        self, prediction: NbaPrediction, subject_is_home: bool, threshold: float,
        home_score: float, away_score: float, minutes_remaining: float,
    ) -> float:
        lead = (
            float(home_score) - float(away_score) if subject_is_home
            else float(away_score) - float(home_score)
        )
        expected_margin = prediction.expected_margin if subject_is_home else -prediction.expected_margin
        return live_spread_probability(
            lead, threshold, minutes_remaining, prediction.margin_sigma, expected_margin)

    def live_total_probability_for(
        self, prediction: NbaPrediction, current_total: float, threshold: float,
        minutes_remaining: float,
    ) -> float:
        return live_total_probability(
            current_total, threshold, minutes_remaining,
            prediction.total_sigma, prediction.expected_total)

    # -- persistence --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": MODEL_VERSION,
            "teams": {key: asdict(value) for key, value in self.teams.items()},
            "processed_game_ids": sorted(self.processed_game_ids),
            "games_seen": self.games_seen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NbaModel":
        return cls(
            teams={key: NbaTeamState(**value) for key, value in data.get("teams", {}).items()},
            processed_game_ids=set(data.get("processed_game_ids", [])),
            games_seen=int(data.get("games_seen", 0)),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path) -> "NbaModel":
        if path.exists():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                pass
        return cls()


# ================================================================ warm gate


def boxscore_games_available(store: BoxscoreStore, team: str, floor: int = MIN_GAMES_FOR_ENGINE) -> int:
    return len(store.recent(team, n=floor))


def is_warm(store: BoxscoreStore, home: str, away: str) -> bool:
    """True iff WS-1's BoxscoreStore has >= MIN_GAMES_FOR_ENGINE games for
    BOTH teams -- the fallback gate (never a half-blend; see module docstring).
    """
    return (
        boxscore_games_available(store, home) >= MIN_GAMES_FOR_ENGINE
        and boxscore_games_available(store, away) >= MIN_GAMES_FOR_ENGINE
    )
