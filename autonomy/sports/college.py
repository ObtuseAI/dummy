"""WS-4: NCAAF + NCAAMB college engines -- reparameterizations, not forks.

NCAAF reuses autonomy/sports/nfl_margin.py's key-number-tilted margin kernel
wholesale (the bisection/tilt machinery is NOT duplicated here -- see
``margin_distribution``'s ``base_pmf`` hook), swapping in a shallower college
|margin| base table (``BASE_ABS_MARGIN_PMF_COLLEGE``) and feeding it an
expected margin that blends this season's team EWMA form with a talent-gap
prior from ``autonomy/sports/elo.py`` early in the season (see
``talent_gap_margin``).

NCAAMB reuses autonomy/sports/nba_model.py's pace x efficiency engine
wholesale via its ``PaceParams`` reparameterization hook (``NCAAMB_PARAMS``
below) -- same ``NbaModel``/``NbaPrediction`` classes, same pace/efficiency/
rest/garbage-time arithmetic, just different cold-start constants. No new
class, no duplicated math.

Both engines are challenger-only (features["challenger_only"]=True, stamped
by the caller in autonomy/signals/sports_intelligence.py) and fail-closed:
missing ESPN data returns None straight through, exactly like every other
engine in this package.

BUILD-TIME PROBES (2026-07-13, network confirmed reachable):

1. neutralSite -- fetched the ESPN NCAAF scoreboard for a Rivalry-Week Saturday
   (``https://site.api.espn.com/apis/site/v2/sports/football/college-football
   /scoreboard?dates=20251129``): 51 events, one of them (401752923, Maryland
   @ Michigan State) carries ``competitions[0]["neutralSite"] == True`` while
   every other event that day carries ``False``. Confirms the exact field
   this module depends on: ``event["competitions"][0]["neutralSite"]``
   (boolean), read from the RAW scoreboard payload (``Game`` itself doesn't
   carry it -- mirrors nhl_model.py's own probable-goalie raw-payload read,
   see ``parse_neutral_site`` below). Also re-probed the NCAAMB scoreboard
   (``.../basketball/mens-college-basketball/scoreboard?dates=20260301``):
   same top-level shape, same field name/path -- one function covers both
   sports.

2. class-year (freshman impact is EXPLICITLY DEFERRED to WS-6; this probe
   only confirms the field exists and records its JSON path for that later
   workstream) -- fetched an NCAAMB team roster
   (``https://site.api.espn.com/apis/site/v2/sports/basketball/
   mens-college-basketball/teams/68/roster``): each entry under
   ``athletes[]`` carries an ``experience`` object, e.g.
   ``{"years": 1, "displayValue": "Freshman", "abbreviation": "FR"}``. Path:
   ``athletes[N].experience.displayValue`` / ``.abbreviation`` / ``.years``.
   Not consumed here.

3. NCAAMB boxscore stat schema -- fetched an NCAAMB game summary
   (``.../basketball/mens-college-basketball/summary?event=401825552``) to
   confirm ``boxscore.teams[].statistics[].name`` matches NBA's schema
   exactly (composite ``fieldGoalsMade-fieldGoalsAttempted`` /
   ``freeThrowsMade-freeThrowsAttempted`` displayValues, plain
   ``offensiveRebounds``/``turnovers`` -- identical to the NBA probe already
   recorded in autonomy/sports/boxscores.py). This confirms it's safe to add
   "ncaamb" to that module's league whitelist so NCAAMB's NbaModel instance
   can actually learn from real games (see boxscores.py's ``_STAT_KEYS``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from autonomy.sports.nba_model import PaceParams
from autonomy.sports.nfl_margin import (
    margin_distribution,
    normal_over_probability,
    spread_cover_probability,
    win_probability,
)
from autonomy.sports.team_scores import LEAGUE_SCORE_CONFIGS, TeamScorePrediction

NCAAF_MODEL_VERSION = "ncaaf_college_kernel_v1"
NCAAMB_MODEL_VERSION = "ncaamb_pace_efficiency_v1"

# =========================================================== NCAAF kernel

# College final |margin| frequencies: key numbers 3 (field goal) and 7
# (touchdown) still spike -- college games still end on the same scoring
# plays -- but roughly 40% shallower than NFL's (more possessions, more
# 2-point/onside-kick/garbage-time variance smear the spike out), and mass
# extends further into the tail (60 vs NFL's 45) since college blowouts run
# much bigger. Curated from public long-run college-football margin shapes,
# same auditable-static-table discipline as nfl_margin.py's own table
# (a propose-then-promote tuning target, not independently fit here).
BASE_ABS_MARGIN_PMF_COLLEGE: dict[int, float] = {
    1: 0.026, 2: 0.021, 3: 0.059, 4: 0.030, 5: 0.022, 6: 0.033, 7: 0.044,
    8: 0.026, 9: 0.017, 10: 0.032, 11: 0.020, 12: 0.017, 13: 0.019,
    14: 0.028, 15: 0.016, 16: 0.017, 17: 0.021, 18: 0.016, 19: 0.014,
    20: 0.020, 21: 0.022, 22: 0.015, 23: 0.014, 24: 0.016, 25: 0.013,
    26: 0.012, 27: 0.013, 28: 0.014, 29: 0.010, 30: 0.012, 31: 0.011,
    32: 0.010, 33: 0.009, 34: 0.009, 35: 0.009, 36: 0.008, 37: 0.007,
    38: 0.008, 39: 0.006, 40: 0.007, 41: 0.006, 42: 0.006, 43: 0.005,
    44: 0.005, 45: 0.005, 46: 0.005, 47: 0.004, 48: 0.004, 49: 0.004,
    50: 0.004, 51: 0.003, 52: 0.003, 53: 0.003, 54: 0.003, 55: 0.003,
    56: 0.002, 57: 0.002, 58: 0.002, 59: 0.002, 60: 0.004,
}

# Talent-gap blend (brief's exact formula): margin = w*ewma_margin +
# (1-w)*elo_margin_pts, w = min(1, games/6). games=0 -> pure Elo (a team's
# EWMA state hasn't observed anything yet this season -- prior-season Elo is
# strictly better information); games>=6 -> pure EWMA (in-season form has
# fully taken over). Linear in games, so monotone between the two ends.
TALENT_GAP_FULL_GAMES = 6.0
ELO_MARGIN_DIVISOR = 25.0  # Elo-point-to-expected-point-margin conversion


def talent_gap_margin(ewma_margin: float, elo_diff: float, games: int) -> tuple[float, float]:
    """(blended_margin, weight) for the NCAAF talent-gap regression.

    Pure function of the three brief-specified inputs -- no TeamScorePrediction/
    neutral-site plumbing here, so this is directly unit-testable against the
    brief's exact games=0 / games>=6 / monotone-between assertions.
    """
    weight = min(1.0, max(0.0, float(games)) / TALENT_GAP_FULL_GAMES)
    elo_margin_pts = float(elo_diff) / ELO_MARGIN_DIVISOR
    margin = weight * float(ewma_margin) + (1.0 - weight) * elo_margin_pts
    return margin, weight


class NcaafCollegeModel:
    """Winner/spread/total pricing for one NCAAF matchup off the college
    key-number kernel.

    Identical machinery to nfl_margin.py::NflMarginModel (same tilted-PMF
    distribution, same win/cover/total helpers, reused by direct import --
    NOT copy-pasted), parameterized with ``BASE_ABS_MARGIN_PMF_COLLEGE`` via
    ``margin_distribution``'s ``base_pmf`` hook. Takes the ALREADY-BLENDED
    margin (talent-gap regression -- see ``talent_gap_margin`` above) and the
    matchup's expected total directly, rather than two raw home/away scores
    like NflMarginModel, since NCAAF's expected margin is not simply
    home_score - away_score.
    """

    def __init__(self, expected_margin: float, expected_total: float, total_sigma: float):
        self.expected_margin = float(expected_margin)
        self.expected_total = float(expected_total)
        self.total_sigma = float(total_sigma)
        self.expected_home_score = (self.expected_total + self.expected_margin) / 2.0
        self.expected_away_score = (self.expected_total - self.expected_margin) / 2.0
        self.distribution = margin_distribution(
            self.expected_margin, base_pmf=BASE_ABS_MARGIN_PMF_COLLEGE)

    def home_win_probability(self) -> float:
        return min(0.995, max(0.005, win_probability(self.distribution)))

    def home_cover_probability(self, line: float) -> float:
        """P(home margin > line); use a negative line for home underdogs."""
        return min(0.995, max(0.005, spread_cover_probability(self.distribution, line)))

    def away_cover_probability(self, line: float) -> float:
        """P(away margin > line) == P(home margin < -line)."""
        return min(0.995, max(0.005, spread_cover_probability(
            {-m: p for m, p in self.distribution.items()}, line)))

    def total_over_probability(self, threshold: float) -> float:
        return normal_over_probability(self.expected_total, self.total_sigma, threshold)


@dataclass(frozen=True)
class NcaafPrediction:
    home_win_probability: float
    expected_home_score: float
    expected_away_score: float
    expected_total: float
    expected_margin: float
    total_sigma: float
    winner_uncertainty: float
    total_uncertainty: float
    sample_games: int
    neutral_site: bool
    talent_gap_weight: float
    model_version: str = NCAAF_MODEL_VERSION


def _cold_uncertainty(sample_games: int) -> tuple[float, float]:
    """(winner_uncertainty, total_uncertainty) -- same cold-start shape as
    autonomy/sports/team_scores.py::TeamScoreModel.predict (a small, widely-
    reused formula, not the kernel/pace arithmetic those modules own)."""
    cold = 1.0 / math.sqrt(1.0 + max(0, sample_games) / 8.0)
    return min(0.42, 0.09 + 0.22 * cold), min(0.44, 0.12 + 0.22 * cold)


def ncaaf_talent_gap_margin(
    prediction: TeamScorePrediction, home_elo: float, away_elo: float,
    games: int, neutral_site: bool,
) -> tuple[float, float]:
    """(blended_margin, weight) folding in neutral-site + the generic ncaaf
    TeamScoreModel's EWMA scores.

    Neutral site is a HARD, ESPN-verified state -> bounded MEAN adjustment:
    the generic model already baked in ncaaf's home_edge_points (see
    LEAGUE_SCORE_CONFIGS["ncaaf"]) when it built expected_home/away_score, so
    a neutral game subtracts that same edge back out of the EWMA margin
    before blending -- it never touches the Elo term (which never carried a
    home bump to begin with, per the brief's exact ``elo_diff`` formula).
    """
    ewma_margin = prediction.expected_home_score - prediction.expected_away_score
    if neutral_site:
        ewma_margin -= LEAGUE_SCORE_CONFIGS["ncaaf"].home_edge_points
    elo_diff = float(home_elo) - float(away_elo)
    return talent_gap_margin(ewma_margin, elo_diff, games)


def ncaaf_college(
    prediction: TeamScorePrediction, home_elo: float, away_elo: float,
    games: int, neutral_site: bool,
) -> tuple[NcaafCollegeModel, NcaafPrediction]:
    """Build the NCAAF college kernel + its reporting/uncertainty wrapper for
    one matchup. Returns (kernel, prediction) -- callers use the kernel for
    win/cover/total pricing and the prediction for reporting + uncertainty
    (see the module docstring lesson: uncertainty must come from THIS
    prediction's fields on the college path, never the generic one's).
    """
    margin, weight = ncaaf_talent_gap_margin(prediction, home_elo, away_elo, games, neutral_site)
    total_sigma = LEAGUE_SCORE_CONFIGS["ncaaf"].total_sigma
    kernel = NcaafCollegeModel(margin, prediction.expected_total, total_sigma)
    winner_unc, total_unc = _cold_uncertainty(games)
    # Soft state (the blend is leaning on a prior-season Elo prior rather
    # than in-season form) -> widen UNCERTAINTY only, never touch the mean
    # (the mean adjustment already happened above, via the blend itself).
    if weight < 1.0:
        widen = 0.03 * (1.0 - weight)
        winner_unc = min(0.48, winner_unc + widen)
        total_unc = min(0.48, total_unc + widen)
    prediction_out = NcaafPrediction(
        home_win_probability=kernel.home_win_probability(),
        expected_home_score=kernel.expected_home_score,
        expected_away_score=kernel.expected_away_score,
        expected_total=kernel.expected_total,
        expected_margin=margin,
        total_sigma=total_sigma,
        winner_uncertainty=winner_unc,
        total_uncertainty=total_unc,
        sample_games=games,
        neutral_site=neutral_site,
        talent_gap_weight=weight,
    )
    return kernel, prediction_out


# =========================================================== NCAAMB engine

# NbaModel reparameterized for men's college basketball (brief's exact
# values). sigma_pace_reference == prior_pace (68, not NBA's 99.5) -- see
# PaceParams' own docstring for why that matters. No new class: NCAAMB
# consumes autonomy/sports/nba_model.py::NbaModel/NbaPrediction directly,
# constructed with these params instead of NBA_PARAMS.
NCAAMB_PARAMS = PaceParams(
    prior_pace=68.0,
    prior_rating=105.0,
    home_edge_points=3.5,
    total_sigma_base=17.0,
    margin_sigma_base=10.5,
    sigma_pace_reference=68.0,
    version=NCAAMB_MODEL_VERSION,
)

# Sanity check recorded here (not asserted at import time -- see
# tests/test_autonomy_college.py): a stone-cold NCAAMB matchup (both teams
# at the prior, no rest adjustment) prices at
#   eff = (prior_rating + prior_rating) / 2 = prior_rating
#   expected_home = prior_pace * eff/100 + home_edge/2
#                 = 68 * 105/100 + 1.75 = 73.15
#   expected_away = 68 * 105/100 - 1.75 = 69.65
#   expected_total = 142.8  (matches the brief's "~141 +/- sigma" target)
# Asserted for real in tests/test_autonomy_college.py rather than at import
# time -- an import-time assert here would take every sports signal down
# with it on a bad edit, not just NCAAMB.


def parse_neutral_site(payload: dict[str, Any] | None) -> dict[str, bool]:
    """game_id -> neutralSite from a raw ESPN scoreboard payload's
    ``competitions[0].neutralSite`` (see PROBE 1 above). Missing/malformed
    entries default False (a genuinely non-neutral game and a parse miss are
    indistinguishable here, and False is the conservative choice -- it keeps
    the existing non-neutral home edge rather than silently zeroing it)."""
    result: dict[str, bool] = {}
    for event in (payload or {}).get("events") or []:
        game_id = str(event.get("id") or "")
        comps = event.get("competitions") or []
        if not game_id or not comps:
            continue
        result[game_id] = bool(comps[0].get("neutralSite", False))
    return result
