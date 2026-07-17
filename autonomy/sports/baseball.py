"""Point-in-time MLB run-distribution challenger.

The model learns only from completed public scoreboard rows.  It estimates
team scoring, prevention, first-inning tendencies, and venue run environment,
then layers the announced starters' season ERA on top.  It is intentionally a
challenger: forecasts are recorded and settled before they can influence live
allocation.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from autonomy.sports.elo import LEAGUE_AVG_ERA
from autonomy.sports.espn import Game
from autonomy.sports.mlb_parks import park_factor_for

# v2 adds park factors, live base-out RE, TTO fatigue, and rest/travel
# uncertainty (WS-11 / spec §4) -- bumped so grading regimes segment the
# distribution shift under a stable source name.
MODEL_VERSION = "mlb_runs_v2_parks"
PRIOR_TEAM_RUNS = 4.35
PRIOR_FIRST_SCORE = 0.30
PRIOR_YRFI = 1.0 - (1.0 - PRIOR_FIRST_SCORE) ** 2
EWMA_ALPHA = 0.08

# -- WS-11: static run-expectancy (RE24-style) table -------------------------
# Expected runs scored in the REST of the current half-inning, given
# (base-occupancy, outs). Values are the widely-published multi-season MLB
# run-expectancy matrix (source: the RE24 table as popularized by Tom Tango /
# Baseball Prospectus from ~2010s play-by-play; the WS-11 brief's own anchors
# -- bases loaded/0 outs ~2.3, empty/2 outs ~0.10 -- match this table almost
# exactly). Base-state keys: "empty", "1st", "2nd", "3rd", "1st_2nd",
# "1st_3rd", "2nd_3rd", "loaded" (see `base_state_key`).
RE24_TABLE: dict[tuple[str, int], float] = {
    ("empty", 0): 0.461, ("empty", 1): 0.243, ("empty", 2): 0.095,
    ("1st", 0): 0.831, ("1st", 1): 0.489, ("1st", 2): 0.214,
    ("2nd", 0): 1.068, ("2nd", 1): 0.644, ("2nd", 2): 0.305,
    ("3rd", 0): 1.277, ("3rd", 1): 0.897, ("3rd", 2): 0.353,
    ("1st_2nd", 0): 1.373, ("1st_2nd", 1): 0.971, ("1st_2nd", 2): 0.466,
    ("1st_3rd", 0): 1.799, ("1st_3rd", 1): 1.135, ("1st_3rd", 2): 0.466,
    ("2nd_3rd", 0): 1.964, ("2nd_3rd", 1): 1.376, ("2nd_3rd", 2): 0.570,
    ("loaded", 0): 2.292, ("loaded", 1): 1.541, ("loaded", 2): 0.736,
}
# The delta below zeroes RE24_TABLE against this game's own expected runs per
# half-inning. Reuses PRIOR_TEAM_RUNS (already the model's own league-average
# runs/team/game prior) rather than fabricating a second "average" constant.
LEAGUE_AVG_HALF_INNING_RUNS = PRIOR_TEAM_RUNS / 9.0

# TTO fatigue: applied only while the current inning is in this window (see
# `tto_fatigue_multiplier` docstring for why this proxy was chosen over a
# precise batters-faced count).
TTO_FATIGUE_INNINGS = (5, 6)
TTO_FATIGUE_MULTIPLIER = 1.12

# Rest/travel: soft, narrative-direction uncertainty widen for a day game
# following a previous night game (see `rest_travel_uncertainty_bump`).
REST_TRAVEL_UNCERTAINTY_BUMP = 0.02
_DAY_GAME_LOCAL_HOUR_CEILING = 14
_NIGHT_GAME_LOCAL_HOUR_FLOOR = 19
# Single-timezone (US/Eastern, EDT = UTC-4) approximation used to convert an
# ESPN UTC start timestamp to a "local" hour. MLB spans multiple US
# timezones, so a West Coast game can be misclassified; the effect is bounded
# to a +0.02 uncertainty WIDEN only (never a mean shift), so the cost of an
# occasional misclassification on this soft/narrative signal is low.
_APPROX_LOCAL_UTC_OFFSET_HOURS = -4


@dataclass
class TeamRunState:
    games: int = 0
    runs_for_ewma: float = PRIOR_TEAM_RUNS
    runs_against_ewma: float = PRIOR_TEAM_RUNS
    first_score_ewma: float = PRIOR_FIRST_SCORE
    first_allow_ewma: float = PRIOR_FIRST_SCORE


@dataclass
class VenueRunState:
    games: int = 0
    total_runs_ewma: float = 2.0 * PRIOR_TEAM_RUNS
    yrfi_ewma: float = PRIOR_YRFI


@dataclass(frozen=True)
class BaseballPrediction:
    home_win_probability: float
    expected_home_runs: float
    expected_away_runs: float
    expected_total_runs: float
    yrfi_probability: float
    winner_uncertainty: float
    total_uncertainty: float
    first_inning_uncertainty: float
    sample_games: int
    pitchers_available: bool
    park_factor: float = 1.0
    model_version: str = MODEL_VERSION


def _ewma(previous: float, value: float, alpha: float = EWMA_ALPHA) -> float:
    return alpha * value + (1.0 - alpha) * previous


def _finite(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def poisson_cdf(k: int, mean: float) -> float:
    """P(X <= k) for a Poisson variable, without a SciPy dependency."""
    if k < 0:
        return 0.0
    mean = max(0.0, float(mean))
    term = math.exp(-mean)
    total = term
    for value in range(1, k + 1):
        term *= mean / value
        total += term
    return min(1.0, max(0.0, total))


def poisson_over_probability(mean: float, threshold: float) -> float:
    """Probability an integer count is strictly greater than a threshold."""
    return min(0.995, max(0.005, 1.0 - poisson_cdf(math.floor(threshold), mean)))


def poisson_win_probability(subject_mean: float, opponent_mean: float) -> float:
    """P(subject wins), splitting the regulation tie mass evenly."""
    limit = max(25, int(math.ceil(max(subject_mean, opponent_mean) + 8.0)))
    subject = [math.exp(-subject_mean)]
    opponent = [math.exp(-opponent_mean)]
    for runs in range(1, limit + 1):
        subject.append(subject[-1] * subject_mean / runs)
        opponent.append(opponent[-1] * opponent_mean / runs)
    probability = 0.0
    opponent_less = 0.0
    for runs, mass in enumerate(subject):
        if runs > 0:
            opponent_less += opponent[runs - 1]
        probability += mass * (opponent_less + 0.5 * opponent[runs])
    return min(0.995, max(0.005, probability))


def poisson_spread_probability(
    subject_mean: float, opponent_mean: float, margin: float
) -> float:
    """P(subject - opponent > margin): subject wins by MORE than `margin` runs.

    The run margin of two independent Poisson scores is Skellam-distributed;
    convolve the PMFs like ``poisson_win_probability``. Runline markets use a
    half-run line (e.g. "win by over 1.5"), so the event is the integer
    ``subject - opponent >= floor(margin) + 1``. Handles negative margins (an
    underdog +line) too: ``floor(margin) + 1`` can be <= 0, where the subject
    tail is the full mass.
    """
    need = math.floor(margin) + 1  # integer run margin strictly above the line
    limit = max(25, int(math.ceil(max(subject_mean, opponent_mean) + 8.0)))
    subject = [math.exp(-subject_mean)]
    opponent = [math.exp(-opponent_mean)]
    for runs in range(1, limit + 1):
        subject.append(subject[-1] * subject_mean / runs)
        opponent.append(opponent[-1] * opponent_mean / runs)
    # subject_tail[k] = P(subject >= k), for k in [0, limit].
    subject_tail = [0.0] * (limit + 2)
    running = 0.0
    for k in range(limit, -1, -1):
        running += subject[k]
        subject_tail[k] = running
    probability = 0.0
    for opponent_runs, opponent_mass in enumerate(opponent):
        k = opponent_runs + need
        if k <= 0:
            tail = 1.0
        elif k > limit:
            tail = 0.0
        else:
            tail = subject_tail[k]
        probability += opponent_mass * tail
    return min(0.995, max(0.005, probability))


def poisson_three_way(subject_mean: float, opponent_mean: float) -> tuple[float, float, float]:
    """(P(subject>opp), P(tie), P(opp>subject)) for two independent Poisson
    scores. A regulation tie is a real outcome (used for the 3-way first-five
    winner market), so tie mass is reported explicitly rather than split."""
    limit = max(25, int(math.ceil(max(subject_mean, opponent_mean) + 8.0)))
    subject = [math.exp(-subject_mean)]
    opponent = [math.exp(-opponent_mean)]
    for runs in range(1, limit + 1):
        subject.append(subject[-1] * subject_mean / runs)
        opponent.append(opponent[-1] * opponent_mean / runs)
    tie = sum(subject[k] * opponent[k] for k in range(limit + 1))
    # P(subject > opponent) = sum_j P(opp=j) * P(subject >= j+1).
    subject_tail = [0.0] * (limit + 2)
    running = 0.0
    for k in range(limit, -1, -1):
        running += subject[k]
        subject_tail[k] = running
    subject_wins = sum(
        opponent[j] * (subject_tail[j + 1] if j + 1 <= limit else 0.0)
        for j in range(limit + 1)
    )
    opponent_wins = max(0.0, 1.0 - tie - subject_wins)
    total = subject_wins + tie + opponent_wins
    if total <= 0:
        return 1 / 3, 1 / 3, 1 / 3
    return subject_wins / total, tie / total, opponent_wins / total


# The first five innings are 5/9 of the game by innings. Scoring is mildly
# front-loaded and, more importantly, F5 is pitched almost entirely by the
# STARTER (no bullpen, TTO penalty still accruing) -- which the run model already
# reflects through the starter's ERA in expected runs. The linear innings share
# plus a widened F5 uncertainty is the honest first-order challenger; the queued
# refinement is a PA-sim F5 distribution (mlb_pa_sim already tracks
# runs_through_5 with starter-dominance and TTO), which captures the
# starter-vs-bullpen gap the linear share cannot.
F5_RUN_SHARE = 5.0 / 9.0


def remaining_innings(current_period: int | None) -> float:
    """Approximate innings left given the current inning (1-based).

    At the start of inning N, N-1 innings are complete, so ~ (9 - (N-1)) remain.
    Extra innings (period > 9) keep a small residual leverage, and the result is
    floored at 0.5 so a live game always carries some remaining variance.
    """
    if not current_period or int(current_period) < 1:
        return 9.0
    return max(0.5, 9.0 - (int(current_period) - 1))


def base_state_key(on_first: bool, on_second: bool, on_third: bool) -> str:
    """Canonical RE24_TABLE base-occupancy key from three runner flags."""
    if on_first and on_second and on_third:
        return "loaded"
    if on_first and on_second:
        return "1st_2nd"
    if on_first and on_third:
        return "1st_3rd"
    if on_second and on_third:
        return "2nd_3rd"
    if on_first:
        return "1st"
    if on_second:
        return "2nd"
    if on_third:
        return "3rd"
    return "empty"


def base_out_delta(base_state: str | None, outs: int | None) -> float:
    """Adjustment to the current half-inning's expected remaining runs.

    Fail-closed: an unknown/missing base-out state (no live play data, or an
    outs value outside the RE24 table's 0/1/2 domain -- e.g. outs==3 at a
    half-inning boundary) is a genuine 0.0 no-op, leaving
    `live_total_probability`'s remaining-mean unchanged.
    """
    if base_state is None or outs is None:
        return 0.0
    value = RE24_TABLE.get((base_state, int(outs)))
    if value is None:
        return 0.0
    return value - LEAGUE_AVG_HALF_INNING_RUNS


def tto_fatigue_multiplier(current_period: int | None) -> float:
    """Times-through-order fatigue proxy: remaining-inning run rate x1.12
    during innings 5-6 of a live game.

    A precise TTO count (batters faced // 9, gated on "starter still in")
    would require correlating the probable starter's athlete id against each
    play's pitcher-participant id across the full play-by-play -- a fragile,
    keyless cross-endpoint join with real bug risk around double switches,
    pinch pitchers, and mid-at-bat relief. Per the WS-11 brief's own
    ambiguity resolution ("if pitcher-change detection from plays is
    undetectable keylessly, apply the x1.12 bump only in innings 5-6 as a
    documented proxy -- do NOT fabricate a precise TTO count you can't
    observe"), this model always uses the inning-window proxy rather than
    attempting that precise count. No `plays` fetch is required for this
    signal at all, which is also why "missing plays" never blocks TTO -- the
    proxy IS the only implementation.
    """
    if current_period is None:
        return 1.0
    return TTO_FATIGUE_MULTIPLIER if int(current_period) in TTO_FATIGUE_INNINGS else 1.0


def _approx_local_hour(start_iso: str | None) -> int | None:
    """Best-effort local hour-of-day from an ESPN UTC start timestamp.

    See `_APPROX_LOCAL_UTC_OFFSET_HOURS` for the single-timezone caveat.
    """
    if not start_iso:
        return None
    match = re.match(r"^\d{4}-\d{2}-\d{2}T(\d{2}):", start_iso)
    if match is None:
        return None
    return (int(match.group(1)) + _APPROX_LOCAL_UTC_OFFSET_HOURS) % 24


def rest_travel_uncertainty_bump(
    current_start_iso: str | None, previous_start_iso: str | None,
) -> float:
    """+0.02 uncertainty widen for a day game following a previous night
    game (SOFT: the direction of any bias is narrative/unknown, so this only
    widens uncertainty -- it never shifts a probability mean). 0.0 no-op
    when either timestamp is missing or the pattern doesn't match.
    """
    current_hour = _approx_local_hour(current_start_iso)
    previous_hour = _approx_local_hour(previous_start_iso)
    if current_hour is None or previous_hour is None:
        return 0.0
    if current_hour < _DAY_GAME_LOCAL_HOUR_CEILING and previous_hour >= _NIGHT_GAME_LOCAL_HOUR_FLOOR:
        return REST_TRAVEL_UNCERTAINTY_BUMP
    return 0.0


def poisson_live_win_probability(
    home_remaining_mean: float, away_remaining_mean: float, home_lead: int
) -> float:
    """P(home wins | current lead) with remaining runs as independent Poissons.

    ``home_lead`` = home_score - away_score right now. Home wins the game when
    ``home_lead + (H - A) > 0`` over the innings still to be played (H, A the
    remaining-run Poissons); the regulation-tie mass (== 0) is split evenly. At
    lead 0 with full-game means it equals ``poisson_win_probability``.
    """
    limit = max(25, int(math.ceil(max(home_remaining_mean, away_remaining_mean) + 8.0)))
    home = [math.exp(-home_remaining_mean)]
    away = [math.exp(-away_remaining_mean)]
    for runs in range(1, limit + 1):
        home.append(home[-1] * home_remaining_mean / runs)
        away.append(away[-1] * away_remaining_mean / runs)
    # home_tail[m] = P(H >= m), for m in [0, limit]; out of range -> 0.
    home_tail = [0.0] * (limit + 2)
    running = 0.0
    for m in range(limit, -1, -1):
        running += home[m]
        home_tail[m] = running
    probability = 0.0
    for away_runs, away_mass in enumerate(away):
        # Home needs H > (away_runs - home_lead) to win; == is a split tie.
        k = away_runs - home_lead
        if k < 0:
            probability += away_mass  # home already ahead regardless of H >= 0
        else:
            win_more = home_tail[k + 1] if (k + 1) <= limit else 0.0
            tie = home[k] if k <= limit else 0.0
            probability += away_mass * (win_more + 0.5 * tie)
    return min(0.9995, max(0.0005, probability))


@dataclass
class BaseballRunModel:
    teams: dict[str, TeamRunState] = field(default_factory=dict)
    venues: dict[str, VenueRunState] = field(default_factory=dict)
    processed_game_ids: set[str] = field(default_factory=set)
    games_seen: int = 0
    league_total_mean: float = 2.0 * PRIOR_TEAM_RUNS
    league_total_m2: float = 0.0

    def _team(self, abbreviation: str) -> TeamRunState:
        return self.teams.setdefault(abbreviation.upper(), TeamRunState())

    def _venue(self, name: str | None) -> VenueRunState | None:
        return self.venues.setdefault(name, VenueRunState()) if name else None

    def update(self, game: Game) -> bool:
        """Apply one fully observed final exactly once."""
        if game.game_id in self.processed_game_ids or game.status != "post":
            return False
        if game.home_score is None or game.away_score is None:
            return False
        home_first = game.home_first_inning_runs
        away_first = game.away_first_inning_runs
        if home_first is None or away_first is None:
            return False

        home = self._team(game.home)
        away = self._team(game.away)
        home.runs_for_ewma = _ewma(home.runs_for_ewma, game.home_score)
        home.runs_against_ewma = _ewma(home.runs_against_ewma, game.away_score)
        away.runs_for_ewma = _ewma(away.runs_for_ewma, game.away_score)
        away.runs_against_ewma = _ewma(away.runs_against_ewma, game.home_score)
        home.first_score_ewma = _ewma(home.first_score_ewma, float(home_first > 0))
        home.first_allow_ewma = _ewma(home.first_allow_ewma, float(away_first > 0))
        away.first_score_ewma = _ewma(away.first_score_ewma, float(away_first > 0))
        away.first_allow_ewma = _ewma(away.first_allow_ewma, float(home_first > 0))
        home.games += 1
        away.games += 1

        total = float(game.home_score + game.away_score)
        self.games_seen += 1
        delta = total - self.league_total_mean
        self.league_total_mean += delta / self.games_seen
        self.league_total_m2 += delta * (total - self.league_total_mean)
        venue = self._venue(game.venue)
        if venue is not None:
            venue.total_runs_ewma = _ewma(venue.total_runs_ewma, total)
            venue.yrfi_ewma = _ewma(venue.yrfi_ewma, float(home_first + away_first > 0))
            venue.games += 1
        self.processed_game_ids.add(game.game_id)
        return True

    @staticmethod
    def _reliability(games: int, full_weight: int = 40) -> float:
        return min(0.85, max(0.0, games / float(full_weight)))

    def _team_metric(self, state: TeamRunState, field_name: str, prior: float) -> float:
        weight = self._reliability(state.games)
        return (1.0 - weight) * prior + weight * float(getattr(state, field_name))

    @staticmethod
    def _pitcher_run_adjustment(era: float | None) -> float:
        value = _finite(era)
        if value is None or value <= 0:
            return 0.0
        return max(-0.9, min(0.9, 0.28 * (value - LEAGUE_AVG_ERA)))

    @staticmethod
    def _pitcher_first_adjustment(era: float | None) -> float:
        value = _finite(era)
        if value is None or value <= 0:
            return 0.0
        return max(-0.08, min(0.08, 0.025 * (value - LEAGUE_AVG_ERA)))

    def predict(self, game: Game) -> BaseballPrediction:
        home = self._team(game.home)
        away = self._team(game.away)
        prior_team = max(3.5, min(5.5, self.league_total_mean / 2.0))
        home_offense = self._team_metric(home, "runs_for_ewma", prior_team)
        home_opponent_defense = self._team_metric(away, "runs_against_ewma", prior_team)
        away_offense = self._team_metric(away, "runs_for_ewma", prior_team)
        away_opponent_defense = self._team_metric(home, "runs_against_ewma", prior_team)
        expected_home = 0.5 * (home_offense + home_opponent_defense)
        expected_away = 0.5 * (away_offense + away_opponent_defense)
        expected_home += self._pitcher_run_adjustment(game.away_pitcher_era)
        expected_away += self._pitcher_run_adjustment(game.home_pitcher_era)

        venue = self.venues.get(game.venue or "")
        if venue is not None and venue.games >= 8:
            venue_weight = min(0.20, venue.games / 250.0)
            venue_factor = max(0.80, min(1.20, venue.total_runs_ewma / 8.7))
            factor = 1.0 + venue_weight * (venue_factor - 1.0)
            expected_home *= factor
            expected_away *= factor
        if game.indoor is not True and game.weather_temperature_f is not None:
            weather_adjustment = max(-0.35, min(0.35, (game.weather_temperature_f - 72.0) * 0.012))
            expected_home += weather_adjustment / 2.0
            expected_away += weather_adjustment / 2.0
        expected_home = max(1.2, min(8.0, expected_home))
        expected_away = max(1.2, min(8.0, expected_away))

        # WS-11: static per-team park factor (autonomy/sports/mlb_parks.py),
        # separate from the venue-name-keyed EWMA learned above. Applies
        # multiplicatively to TOTALS/YRFI only -- winner/spread stay on the
        # unscaled expected_home_runs/expected_away_runs, so a park factor of
        # 1.0 (unknown park) is a byte-identical no-op everywhere.
        park_factor = park_factor_for(game.home)

        home_first = 0.5 * (
            self._team_metric(home, "first_score_ewma", PRIOR_FIRST_SCORE)
            + self._team_metric(away, "first_allow_ewma", PRIOR_FIRST_SCORE)
        ) + self._pitcher_first_adjustment(game.away_pitcher_era)
        away_first = 0.5 * (
            self._team_metric(away, "first_score_ewma", PRIOR_FIRST_SCORE)
            + self._team_metric(home, "first_allow_ewma", PRIOR_FIRST_SCORE)
        ) + self._pitcher_first_adjustment(game.home_pitcher_era)
        home_first *= park_factor
        away_first *= park_factor
        home_first = max(0.06, min(0.70, home_first))
        away_first = max(0.06, min(0.70, away_first))
        yrfi = 1.0 - (1.0 - home_first) * (1.0 - away_first)
        if venue is not None and venue.games >= 12:
            venue_weight = min(0.15, venue.games / 300.0)
            yrfi = (1.0 - venue_weight) * yrfi + venue_weight * venue.yrfi_ewma

        sample = min(home.games, away.games)
        cold = 1.0 / math.sqrt(1.0 + sample / 8.0)
        pitchers = game.home_pitcher_era is not None and game.away_pitcher_era is not None
        missing_pitcher_penalty = 0.04 if not pitchers else 0.0
        return BaseballPrediction(
            home_win_probability=poisson_win_probability(expected_home, expected_away),
            expected_home_runs=expected_home,
            expected_away_runs=expected_away,
            expected_total_runs=(expected_home + expected_away) * park_factor,
            yrfi_probability=min(0.95, max(0.05, yrfi)),
            winner_uncertainty=min(0.40, 0.07 + 0.18 * cold + missing_pitcher_penalty),
            total_uncertainty=min(0.42, 0.11 + 0.18 * cold + missing_pitcher_penalty),
            first_inning_uncertainty=min(0.42, 0.13 + 0.18 * cold + missing_pitcher_penalty),
            sample_games=sample,
            pitchers_available=pitchers,
            park_factor=park_factor,
        )

    def total_probability(self, prediction: BaseballPrediction, threshold: float) -> float:
        return poisson_over_probability(prediction.expected_total_runs, threshold)

    def spread_probability(
        self, prediction: BaseballPrediction, subject_is_home: bool, margin: float
    ) -> float:
        """P(subject wins by more than `margin` runs) via the run-margin Skellam."""
        if subject_is_home:
            return poisson_spread_probability(
                prediction.expected_home_runs, prediction.expected_away_runs, margin
            )
        return poisson_spread_probability(
            prediction.expected_away_runs, prediction.expected_home_runs, margin
        )

    def team_total_probability(
        self, prediction: BaseballPrediction, subject_is_home: bool, threshold: float
    ) -> float:
        """P(one team scores more than `threshold` runs). A team's run count is
        Poisson at its expected runs; team totals are a total-family market, so
        the park factor applies (mirrors ``total_probability``)."""
        mean = prediction.expected_home_runs if subject_is_home else prediction.expected_away_runs
        return poisson_over_probability(mean * prediction.park_factor, threshold)

    def f5_total_probability(self, prediction: BaseballPrediction, threshold: float) -> float:
        """P(first-five combined runs over `threshold`)."""
        return poisson_over_probability(prediction.expected_total_runs * F5_RUN_SHARE, threshold)

    def f5_spread_probability(
        self, prediction: BaseballPrediction, subject_is_home: bool, margin: float
    ) -> float:
        """P(subject leads the first five by more than `margin` runs)."""
        home = prediction.expected_home_runs * F5_RUN_SHARE
        away = prediction.expected_away_runs * F5_RUN_SHARE
        if subject_is_home:
            return poisson_spread_probability(home, away, margin)
        return poisson_spread_probability(away, home, margin)

    def f5_outcome_probabilities(
        self, prediction: BaseballPrediction
    ) -> tuple[float, float, float]:
        """(P(home leads F5), P(F5 tie), P(away leads F5)) for the 3-way market.

        A first-five tie is a real, tradeable outcome, so the three legs are
        reported separately and sum to 1."""
        home = prediction.expected_home_runs * F5_RUN_SHARE
        away = prediction.expected_away_runs * F5_RUN_SHARE
        return poisson_three_way(home, away)

    def live_win_probability(
        self,
        prediction: BaseballPrediction,
        home_score: int,
        away_score: int,
        remaining_innings: float,
    ) -> float:
        """Live P(home wins) given the current score and innings left to play.

        Scales the pre-game per-game run rates down to the innings remaining and
        shifts by the current lead. At the start (remaining_innings == 9, score
        0-0) it reduces to the pre-game ``home_win_probability``.
        """
        fraction = max(0.0, float(remaining_innings)) / 9.0
        home_remaining = prediction.expected_home_runs * fraction
        away_remaining = prediction.expected_away_runs * fraction
        return poisson_live_win_probability(
            home_remaining, away_remaining, int(home_score) - int(away_score)
        )

    def live_total_probability(
        self,
        prediction: BaseballPrediction,
        current_total_runs: int,
        threshold: float,
        remaining_innings: float,
        base_state: str | None = None,
        outs: int | None = None,
        current_period: int | None = None,
    ) -> float:
        """Live P(final total > threshold): runs already in plus the rest.

        Only the runs still to come are random (Poisson over the innings left),
        shifted by what's already scored. At the start it reduces to
        ``total_probability``.

        WS-11 adds two independent, fail-closed adjustments to the remaining
        mean, both defaulting to a no-op (byte-identical to the pre-WS11
        signature when omitted):
          - ``base_state``/``outs``: the static RE24 table (see
            `base_out_delta`) adjusts the CURRENT half-inning's remaining
            runs only -- a hard, verifiable state, so it may shift the mean.
          - ``current_period``: the TTO fatigue proxy (see
            `tto_fatigue_multiplier`) scales the whole remaining-mean by
            1.12x during innings 5-6.
        """
        fraction = max(0.0, float(remaining_innings)) / 9.0
        remaining_mean = prediction.expected_total_runs * fraction
        remaining_mean = max(0.0, remaining_mean + base_out_delta(base_state, outs))
        remaining_mean *= tto_fatigue_multiplier(current_period)
        return poisson_over_probability(remaining_mean, threshold - int(current_total_runs))

    def live_spread_probability(
        self,
        prediction: BaseballPrediction,
        subject_is_home: bool,
        margin: float,
        home_score: int,
        away_score: int,
        remaining_innings: float,
    ) -> float:
        """Live P(subject wins by more than `margin`) given the current lead.

        The remaining-run margin is Skellam over the innings left, shifted by the
        lead already banked. At the start it reduces to ``spread_probability``.
        """
        fraction = max(0.0, float(remaining_innings)) / 9.0
        if subject_is_home:
            subject_mean = prediction.expected_home_runs * fraction
            opponent_mean = prediction.expected_away_runs * fraction
            current_lead = int(home_score) - int(away_score)
        else:
            subject_mean = prediction.expected_away_runs * fraction
            opponent_mean = prediction.expected_home_runs * fraction
            current_lead = int(away_score) - int(home_score)
        return poisson_spread_probability(subject_mean, opponent_mean, margin - current_lead)

    def to_dict(self) -> dict[str, Any]:
        variance = (
            self.league_total_m2 / (self.games_seen - 1) if self.games_seen > 1 else None
        )
        return {
            "model_version": MODEL_VERSION,
            "teams": {key: asdict(value) for key, value in self.teams.items()},
            "venues": {key: asdict(value) for key, value in self.venues.items()},
            "processed_game_ids": sorted(self.processed_game_ids),
            "games_seen": self.games_seen,
            "league_total_mean": self.league_total_mean,
            "league_total_m2": self.league_total_m2,
            "league_total_variance": variance,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaseballRunModel":
        return cls(
            teams={key: TeamRunState(**value) for key, value in data.get("teams", {}).items()},
            venues={key: VenueRunState(**value) for key, value in data.get("venues", {}).items()},
            processed_game_ids=set(data.get("processed_game_ids", [])),
            games_seen=int(data.get("games_seen", 0)),
            league_total_mean=float(data.get("league_total_mean", 2.0 * PRIOR_TEAM_RUNS)),
            league_total_m2=float(data.get("league_total_m2", 0.0)),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path) -> "BaseballRunModel":
        if path.exists():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                pass
        return cls()
