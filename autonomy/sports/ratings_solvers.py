"""In-house Massey + Colley rating sources (Phenon Harness WS-A1b).

Two more `RatingSource`s (see `autonomy.sports.power_ratings.RatingSource`)
for the power-ratings ensemble, computed FROM public settled game results we
already fetch via `autonomy.sports.espn.EspnClient.games` -- we REPLICATE the
published Massey and Colley rating METHODS, we do NOT scrape
masseyratings.com / DRatings / any paid site. Pure Python throughout: the
rest of `autonomy/` deliberately imports no numpy/scipy, so both solves run
on a hand-rolled Gauss-Seidel iterative solver (`solve_spd`) rather than a
matrix-library inverse.

Fail-closed & point-in-time (same discipline as every other RatingSource in
this module):
  - Only `status == "post"` games with both scores present and a resolved
    `home_won` feed either solve -- never live/pre games (mirrors
    `SportsEloSignal.warmup`'s own fetch+filter, see `_settled_results`).
  - A league that has never been warmed (`warmup` not called, or called with
    zero usable games) holds no ratings for that league at all --
    `.rating()` returns None for every team, byte-identical to the source
    being absent.
  - A team with fewer than `MIN_GAMES_PER_TEAM` settled games this season is
    too thin to trust even though the solver still assigns it a number (the
    solve happens over the WHOLE graph at once) -- `.rating()` returns None
    for that team specifically.
  - Solver non-convergence or a degenerate (zero-pivot) system fails the
    WHOLE league closed -- `.rating()` returns None for every team in it.
  - Neither source ever calls any model's `.update()` -- these are pure
    reads of ESPN's settled-game feed, nothing here has a learning path to
    leak into.

Massey (ridge least-squares over point margins) -- native points,
`points_per_unit == 1.0`. Colley (win-loss matrix) -- dimensionless [0, 1],
needs a documented per-league point-scale (`COLLEY_POINTS_PER_UNIT`, a
propose-then-promote tuner candidate, same convention as
`power_ratings.ELO_POINTS_PER_MARGIN` / `nfl_margin.BASE_ABS_MARGIN_PMF`).
"""
from __future__ import annotations

import math
from typing import Any, Iterable

from autonomy.sports.espn import Game, canonical_team

# ---------------------------------------------------------------------------
# Tuner-candidate constants (propose-then-promote, never independently fit)
# ---------------------------------------------------------------------------

# Ridge shrinkage added to the Massey normal-equation diagonal. Small
# relative to a real season's per-team game count (NFL ~17, NCAAF/NCAAMB/NBA
# far more) so the solved differences stay close to average scoring margins
# rather than collapsing toward zero; large enough that MtM (otherwise
# singular -- Massey's un-regularized system has rank n-1, one team's rating
# floating free) becomes strictly positive-definite with no separate
# sum-to-zero constraint needed. See the module docstring's fail-closed note
# and `tests/test_autonomy_ratings_solvers.py`'s hand-checked 3-team example
# for a concrete before/after.
RIDGE_LAMBDA = 1.0

# A team with fewer than this many settled games this season is too thin to
# trust even though the solver still assigns it a rating (the solve runs
# over the whole graph at once, not per team) -- `MasseyRatingSource.rating`
# / `ColleyRatingSource.rating` return None for such a team.
MIN_GAMES_PER_TEAM = 3

# Colley ratings are dimensionless, centered at 0.5, spanning roughly
# [0, 1] over a season (win-loss-derived ordinal strength, scores unused).
# A full-spread Colley diff (~[-0.5, +0.5]) is mapped to roughly the
# league's strong-favorite margin in POINTS -- rough starting points, NOT
# independently fit, promotable via the tuner like every other per-league
# scaling constant in this module family (see
# `power_ratings.ELO_POINTS_PER_MARGIN`). None => unsupported league =>
# the source is dropped from the ensemble for it, same fail-closed contract
# as every other `points_per_unit`.
COLLEY_POINTS_PER_UNIT: dict[str, float] = {
    "nfl": 28.0,
    "ncaaf": 28.0,
    "nba": 40.0,
    "ncaamb": 40.0,
}

# Solver-tolerance tuner candidates (propose-then-promote, like RIDGE_LAMBDA
# above): 10000 sweeps comfortably converges even a ~360-team college-league
# season system (NCAAF/NCAAMB) that's only weakly diagonally dominant, and is
# cheap since `solve_spd` runs once per warmup, not per cycle; 1e-7 is tight
# enough for point-margin accuracy (a rating error of 1e-7 points is
# irrelevant) without needlessly forcing extra sweeps on large leagues.
_MAX_ITER = 10000
_TOL = 1e-7


# ---------------------------------------------------------------------------
# Pure-Python SPD solver (Gauss-Seidel)
# ---------------------------------------------------------------------------


def solve_spd(
    A: list[list[float]], b: list[float], max_iter: int = _MAX_ITER, tol: float = _TOL
) -> list[float] | None:
    """Solve `A x = b` via Gauss-Seidel iteration; None on non-convergence.

    Both the ridge-regularized Massey normal-equation matrix and the Colley
    matrix are symmetric, positive-definite, and (strictly) diagonally
    dominant by construction, so Gauss-Seidel is mathematically guaranteed
    to converge for either -- this is deliberately NOT a general-purpose
    linear solver. A zero diagonal entry (degenerate/malformed system) fails
    closed immediately rather than dividing by zero; a non-finite update
    (a genuinely non-diagonally-dominant caller-supplied matrix diverging)
    or exhausting `max_iter` without reaching `tol` also fails closed to
    None -- callers must treat None as "no solution this cycle", never
    raise or fabricate a partial answer.
    """
    n = len(b)
    if n == 0:
        return []
    for i in range(n):
        if A[i][i] == 0:
            return None
    x = [0.0] * n
    for _ in range(max_iter):
        max_delta = 0.0
        for i in range(n):
            row = A[i]
            s = b[i] - sum(row[j] * x[j] for j in range(n) if j != i)
            new_xi = s / row[i]
            if not math.isfinite(new_xi):
                return None
            max_delta = max(max_delta, abs(new_xi - x[i]))
            x[i] = new_xi
        if max_delta < tol:
            return x
    return None


# ---------------------------------------------------------------------------
# Point-in-time game extraction (mirrors SportsEloSignal.warmup's filter)
# ---------------------------------------------------------------------------


def settled_results(games: Iterable[Game], league: str) -> list[tuple[str, str, float, bool]]:
    """(home, away, margin, home_won) for settled, both-scored games only.

    Filter mirrors `SportsEloSignal.warmup`: `status == "post"` AND
    `home_won is not None`, plus (Massey-specific) both scores present --
    never a live/pre game. Team names are canonicalized via
    `autonomy.sports.espn.canonical_team` so aliases (e.g. MLB's AZ/ARI,
    CWS/CHW) collapse to one identity, same as every other RatingSource.
    """
    out: list[tuple[str, str, float, bool]] = []
    for g in games:
        if g.status != "post" or g.home_won is None:
            continue
        if g.home_score is None or g.away_score is None:
            continue
        home = canonical_team(league, g.home)
        away = canonical_team(league, g.away)
        out.append((home, away, float(g.home_score - g.away_score), bool(g.home_won)))
    return out


# ---------------------------------------------------------------------------
# Massey: ridge least-squares over point margins
# ---------------------------------------------------------------------------


def build_massey_system(
    results: list[tuple[str, str, float, bool]],
) -> tuple[list[str], dict[str, int], list[list[float]], list[float], dict[str, int]]:
    """Assemble the Massey normal-equation system directly (no G x n design
    matrix materialized): for each game, `A[h][h] += 1`, `A[a][a] += 1`,
    `A[h][a] -= 1`, `A[a][h] -= 1`, `b[h] += margin`, `b[a] -= margin`."""
    teams = sorted({t for h, a, _, _ in results for t in (h, a)})
    index = {team: i for i, team in enumerate(teams)}
    n = len(teams)
    A = [[0.0] * n for _ in range(n)]
    b = [0.0] * n
    games_played = {team: 0 for team in teams}
    for home, away, margin, _ in results:
        h, a = index[home], index[away]
        A[h][h] += 1.0
        A[a][a] += 1.0
        A[h][a] -= 1.0
        A[a][h] -= 1.0
        b[h] += margin
        b[a] -= margin
        games_played[home] += 1
        games_played[away] += 1
    return teams, index, A, b, games_played


def solve_massey(
    results: list[tuple[str, str, float, bool]], ridge_lambda: float = RIDGE_LAMBDA
) -> tuple[dict[str, float] | None, dict[str, int]]:
    """Solve the ridge-regularized Massey system. Returns (ratings, games_played);
    ratings is None on zero games or solver non-convergence (fail-closed)."""
    teams, index, A, b, games_played = build_massey_system(results)
    if not teams:
        return None, {}
    for i in range(len(teams)):
        A[i][i] += ridge_lambda
    x = solve_spd(A, b)
    if x is None:
        return None, games_played
    return {team: x[index[team]] for team in teams}, games_played


class MasseyRatingSource:
    """In-house Massey rating source: `points_per_unit` is native points (1.0)."""

    name = "massey"

    def __init__(self, espn: Any = None) -> None:
        self._espn = espn
        self._ratings: dict[str, dict[str, float]] = {}
        self._games_played: dict[str, dict[str, int]] = {}
        # Leagues this instance has actually been warmed for (as opposed to
        # ones that warmed to zero usable games) -- drives points_per_unit
        # independent of whether the solve itself succeeded, same shape as
        # `_CachedPowerIndexSource.points_per_unit` checking league support
        # rather than fetch success.
        self._supported: set[str] = set()

    def warmup(self, league: str, date_ranges: list[str]) -> None:
        """Fetch settled games over `date_ranges` (mirrors
        `SportsEloSignal.warmup`'s fetch-then-filter shape) and solve. Zero
        usable games (offseason, dead feed, non-convergent solve) leaves
        this league's ratings empty -- `.rating` then returns None for
        every team, byte-identical to the source being absent."""
        self._supported.add(league)
        games: list[Game] = []
        for dates in date_ranges:
            games.extend(self._espn.games(league, dates))
        results = settled_results(games, league)
        ratings, games_played = solve_massey(results)
        self._ratings[league] = ratings or {}
        self._games_played[league] = games_played

    def rating(self, league: str, team: str) -> float | None:
        ratings = self._ratings.get(league)
        if not ratings:
            return None
        key = canonical_team(league, team)
        if self._games_played.get(league, {}).get(key, 0) < MIN_GAMES_PER_TEAM:
            return None
        return ratings.get(key)

    def points_per_unit(self, league: str) -> float | None:
        # Massey ratings are already in POINT units (a rating diff is
        # already an expected point margin) -- 1.0 for any league this
        # instance has been warmed for, else None (fail-closed, same as an
        # unwarmed EloModel dropping the league entirely).
        return 1.0 if league in self._supported else None


# ---------------------------------------------------------------------------
# Colley: win-loss matrix
# ---------------------------------------------------------------------------


def build_colley_system(
    results: list[tuple[str, str, float, bool]],
) -> tuple[list[str], dict[str, int], list[list[float]], list[float], dict[str, int]]:
    """Assemble the Colley matrix: `C_ii = 2 + n_i`, `C_ij = -n_ij`,
    `b_i = 1 + (w_i - l_i) / 2`. Scores are unused -- pure win-loss."""
    teams = sorted({t for h, a, _, _ in results for t in (h, a)})
    index = {team: i for i, team in enumerate(teams)}
    n = len(teams)
    C = [[0.0] * n for _ in range(n)]
    wins = {team: 0.0 for team in teams}
    losses = {team: 0.0 for team in teams}
    games_played = {team: 0 for team in teams}
    for home, away, _margin, home_won in results:
        h, a = index[home], index[away]
        C[h][h] += 1.0
        C[a][a] += 1.0
        C[h][a] -= 1.0
        C[a][h] -= 1.0
        games_played[home] += 1
        games_played[away] += 1
        if home_won:
            wins[home] += 1.0
            losses[away] += 1.0
        else:
            wins[away] += 1.0
            losses[home] += 1.0
    b = [0.0] * n
    for team, i in index.items():
        C[i][i] += 2.0
        b[i] = 1.0 + (wins[team] - losses[team]) / 2.0
    return teams, index, C, b, games_played


def solve_colley(
    results: list[tuple[str, str, float, bool]],
) -> tuple[dict[str, float] | None, dict[str, int]]:
    """Solve the Colley system. Returns (ratings, games_played); ratings is
    None on zero games or solver non-convergence (fail-closed)."""
    teams, index, C, b, games_played = build_colley_system(results)
    if not teams:
        return None, {}
    x = solve_spd(C, b)
    if x is None:
        return None, games_played
    return {team: x[index[team]] for team in teams}, games_played


class ColleyRatingSource:
    """In-house Colley rating source: dimensionless, `points_per_unit`
    comes from the documented `COLLEY_POINTS_PER_UNIT` tuner-candidate table."""

    name = "colley"

    def __init__(self, espn: Any = None) -> None:
        self._espn = espn
        self._ratings: dict[str, dict[str, float]] = {}
        self._games_played: dict[str, dict[str, int]] = {}

    def warmup(self, league: str, date_ranges: list[str]) -> None:
        games: list[Game] = []
        for dates in date_ranges:
            games.extend(self._espn.games(league, dates))
        results = settled_results(games, league)
        ratings, games_played = solve_colley(results)
        self._ratings[league] = ratings or {}
        self._games_played[league] = games_played

    def rating(self, league: str, team: str) -> float | None:
        ratings = self._ratings.get(league)
        if not ratings:
            return None
        key = canonical_team(league, team)
        if self._games_played.get(league, {}).get(key, 0) < MIN_GAMES_PER_TEAM:
            return None
        return ratings.get(key)

    def points_per_unit(self, league: str) -> float | None:
        return COLLEY_POINTS_PER_UNIT.get(league)
