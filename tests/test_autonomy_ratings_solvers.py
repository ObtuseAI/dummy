"""Tests for autonomy.sports.ratings_solvers (Phenon Harness WS-A1b).

Zero network: every source is warmed via a tiny fake ESPN client exposing
only `.games(league, dates) -> list[Game]`, hand-built `Game` fixtures, and
hand-checked linear-algebra examples (3-team round robins solved by hand
and cross-checked against the pure-Python Gauss-Seidel solver).
"""
from __future__ import annotations

import math

import pytest

from autonomy.sports.espn import Game
from autonomy.sports.ratings_solvers import (
    COLLEY_POINTS_PER_UNIT,
    MIN_GAMES_PER_TEAM,
    RIDGE_LAMBDA,
    ColleyRatingSource,
    MasseyRatingSource,
    build_colley_system,
    build_massey_system,
    settled_results,
    solve_colley,
    solve_massey,
    solve_spd,
)


class FakeEspnClient:
    """Duck-typed ESPN client stand-in: only `.games()` is ever called."""

    def __init__(self, games_by_key: dict[tuple[str, str], list[Game]]) -> None:
        self._games_by_key = games_by_key
        self.calls: list[tuple[str, str]] = []

    def games(self, league: str, dates: str | None = None) -> list[Game]:
        self.calls.append((league, dates))
        return self._games_by_key.get((league, dates), [])


def _post_game(game_id, league, home, away, home_score, away_score, date="2026-01-01"):
    return Game(
        game_id, league, home, away, "post", home_score > away_score, date,
        home_score=home_score, away_score=away_score,
    )


# ---------------------------------------------------------------------------
# 1. Massey correctness (hand-checked 3-team round robin)
# ---------------------------------------------------------------------------
#
# A beats B by 10, B beats C by 6, A beats C by 16 -- a perfectly transitive
# (consistent) set of margins, chosen so the ridge-regularized solve has a
# clean closed form. Normal-equation assembly (RIDGE_LAMBDA == 1.0):
#   A = [[2+1, -1, -1], [-1, 2+1, -1], [-1, -1, 2+1]] = [[3,-1,-1],[-1,3,-1],[-1,-1,3]]
#   b = [26, -4, -22]
# Solving by hand (elimination, using the ridge-induced x+y+z=0 identity):
#   rA=6.5, rB=-1.0, rC=-5.5  (diffs: rA-rB=7.5, rB-rC=4.5, rA-rC=12.0 --
#   each exactly 75% of the raw margin, the ridge shrinkage factor for this
#   fully-consistent 3-node/3-edge graph.)


def test_massey_hand_checked_3team_round_robin():
    results = [
        ("A", "B", 10.0, True),
        ("B", "C", 6.0, True),
        ("A", "C", 16.0, True),
    ]

    ratings, games_played = solve_massey(results)

    assert ratings is not None
    assert ratings["A"] == pytest.approx(6.5, abs=1e-6)
    assert ratings["B"] == pytest.approx(-1.0, abs=1e-6)
    assert ratings["C"] == pytest.approx(-5.5, abs=1e-6)
    # Rating order matches on-field results.
    assert ratings["A"] > ratings["B"] > ratings["C"]
    # Diffs are the ridge-shrunk (75%) version of the raw margins -- not
    # equal to the raw margins, but proportionally consistent with them.
    assert ratings["A"] - ratings["B"] == pytest.approx(7.5, abs=1e-6)
    assert ratings["B"] - ratings["C"] == pytest.approx(4.5, abs=1e-6)
    assert ratings["A"] - ratings["C"] == pytest.approx(12.0, abs=1e-6)
    assert games_played == {"A": 2, "B": 2, "C": 2}


def test_massey_build_system_matches_hand_derivation():
    results = [
        ("A", "B", 10.0, True),
        ("B", "C", 6.0, True),
        ("A", "C", 16.0, True),
    ]
    teams, index, A, b, games_played = build_massey_system(results)

    assert teams == ["A", "B", "C"]
    assert A == [[2.0, -1.0, -1.0], [-1.0, 2.0, -1.0], [-1.0, -1.0, 2.0]]
    assert b == [26.0, -4.0, -22.0]


def test_massey_points_per_unit_is_native_one():
    espn = FakeEspnClient({("nfl", "d1"): [
        _post_game("g1", "nfl", "A", "B", 20, 10),
        _post_game("g2", "nfl", "B", "C", 16, 10),
        _post_game("g3", "nfl", "A", "C", 26, 10),
    ]})
    source = MasseyRatingSource(espn=espn)
    source.warmup("nfl", ["d1"])

    assert source.points_per_unit("nfl") == 1.0
    assert source.points_per_unit("not_a_league") is None


# ---------------------------------------------------------------------------
# 2. Colley correctness (canonical worked 3-team example)
# ---------------------------------------------------------------------------
#
# A beats B, A beats C, B beats C (A undefeated 2-0, B split 1-1, C winless
# 0-2). This is the textbook Colley 3-team worked example:
#   C = [[4,-1,-1],[-1,4,-1],[-1,-1,4]], b = [2, 1, 0]
#   => rA=0.7, rB=0.5, rC=0.3 (sum == 1.5 == n/2, centered on 0.5).


def test_colley_hand_checked_3team_canonical_example():
    results = [
        ("A", "B", 5.0, True),
        ("A", "C", 5.0, True),
        ("B", "C", 5.0, True),
    ]

    ratings, games_played = solve_colley(results)

    assert ratings is not None
    assert ratings["A"] == pytest.approx(0.7, abs=1e-6)
    assert ratings["B"] == pytest.approx(0.5, abs=1e-6)
    assert ratings["C"] == pytest.approx(0.3, abs=1e-6)
    assert ratings["A"] > ratings["B"] > ratings["C"]  # undefeated highest, winless lowest
    assert sum(ratings.values()) == pytest.approx(1.5, abs=1e-6)  # n/2
    assert games_played == {"A": 2, "B": 2, "C": 2}


def test_colley_build_system_matches_hand_derivation():
    results = [
        ("A", "B", 5.0, True),
        ("A", "C", 5.0, True),
        ("B", "C", 5.0, True),
    ]
    teams, index, C, b, games_played = build_colley_system(results)

    assert teams == ["A", "B", "C"]
    assert C == [[4.0, -1.0, -1.0], [-1.0, 4.0, -1.0], [-1.0, -1.0, 4.0]]
    assert b == [2.0, 1.0, 0.0]


def test_colley_scores_do_not_affect_rating_only_win_loss():
    # A blowout margin must not move the Colley rating -- only who won.
    results_blowout = [("A", "B", 50.0, True), ("A", "C", 50.0, True), ("B", "C", 1.0, True)]
    results_close = [("A", "B", 1.0, True), ("A", "C", 1.0, True), ("B", "C", 1.0, True)]

    ratings_blowout, _ = solve_colley(results_blowout)
    ratings_close, _ = solve_colley(results_close)

    assert ratings_blowout == ratings_close


def test_colley_tie_is_half_win_half_loss_for_each_team():
    ratings, games_played = solve_colley([("A", "B", 0.0, None)])

    assert ratings == pytest.approx({"A": 0.5, "B": 0.5}, abs=1e-6)
    assert games_played == {"A": 1, "B": 1}


def test_settled_results_includes_explicit_tie_but_not_unresolved_post():
    games = [
        Game(
            "tie", "nfl", "A", "B", "post", None, "2026-01-01",
            home_score=20, away_score=20, is_tie=True,
        ),
        Game(
            "unknown", "nfl", "C", "D", "post", None, "2026-01-01",
            home_score=20, away_score=20,
        ),
    ]

    assert settled_results(games, "nfl") == [("A", "B", 0.0, None)]


def test_colley_points_per_unit_documented_table():
    espn = FakeEspnClient({("nfl", "d1"): [
        _post_game("g1", "nfl", "A", "B", 20, 10),
        _post_game("g2", "nfl", "A", "C", 20, 10),
        _post_game("g3", "nfl", "B", "C", 20, 10),
    ]})
    source = ColleyRatingSource(espn=espn)
    source.warmup("nfl", ["d1"])

    assert source.points_per_unit("nfl") == COLLEY_POINTS_PER_UNIT["nfl"]
    assert source.points_per_unit("ncaaf") == COLLEY_POINTS_PER_UNIT["ncaaf"]
    assert source.points_per_unit("nba") == COLLEY_POINTS_PER_UNIT["nba"]
    assert source.points_per_unit("ncaamb") == COLLEY_POINTS_PER_UNIT["ncaamb"]
    assert source.points_per_unit("not_a_league") is None


# ---------------------------------------------------------------------------
# 3. Solver convergence: known SPD system + degenerate/non-convergent system
# ---------------------------------------------------------------------------


def test_solve_spd_matches_known_reference_solution():
    # Diagonal (trivially diagonally-dominant) system with an exact,
    # unambiguous hand-checked solution: 3x = 6 -> x = 2; 5y = 15 -> y = 3.
    A = [[3.0, 0.0], [0.0, 5.0]]
    b = [6.0, 15.0]

    x = solve_spd(A, b)

    assert x is not None
    assert x[0] == pytest.approx(2.0, abs=1e-6)
    assert x[1] == pytest.approx(3.0, abs=1e-6)


def test_solve_spd_diagonally_dominant_coupled_system():
    # [[4,-1],[-1,4]] x = [3, 5] -- diagonally dominant, hand-solvable:
    # 4x - y = 3; -x + 4y = 5 => x = (3+y)/4; sub: -( (3+y)/4 ) + 4y = 5
    # => -3-y+16y=20 => 15y=23 => y=23/15; x=(3+23/15)/4 = (68/15)/4=17/15
    A = [[4.0, -1.0], [-1.0, 4.0]]
    b = [3.0, 5.0]

    x = solve_spd(A, b)

    assert x is not None
    assert x[0] == pytest.approx(17.0 / 15.0, abs=1e-6)
    assert x[1] == pytest.approx(23.0 / 15.0, abs=1e-6)


def test_solve_spd_zero_pivot_returns_none():
    A = [[0.0, 1.0], [1.0, 2.0]]
    b = [1.0, 2.0]

    assert solve_spd(A, b) is None


def test_solve_spd_non_diagonally_dominant_diverges_to_none():
    # Off-diagonal magnitude exceeds the diagonal -- Gauss-Seidel is not
    # guaranteed to converge here, and this particular system diverges.
    A = [[1.0, 2.0], [2.0, 1.0]]
    b = [1.0, 1.0]

    assert solve_spd(A, b, max_iter=50, tol=1e-12) is None


def test_solve_spd_empty_system_returns_empty_list():
    assert solve_spd([], []) == []


# ---------------------------------------------------------------------------
# 4. Consensus integration: magnitude sanity (mirrors WS-A1-fix's own test)
# ---------------------------------------------------------------------------


def test_massey_plus_elo_consensus_lands_in_sane_single_digit_range():
    from autonomy.sports.power_ratings import EloSource, consensus_margin

    class SpyEloModel:
        def __init__(self, ratings):
            self.ratings = ratings

        def rating(self, team):
            return self.ratings.get(team, 1500.0)

        def update(self, *a, **k):
            raise AssertionError("must never update")

    espn = FakeEspnClient({("nfl", "d1"): [
        _post_game("g1", "nfl", "KC", "DEN", 27, 20),
        _post_game("g2", "nfl", "KC", "LV", 24, 17),
        _post_game("g3", "nfl", "KC", "LAC", 30, 24),
        _post_game("g4", "nfl", "DEN", "LV", 20, 17),
        _post_game("g5", "nfl", "DEN", "LAC", 23, 20),
        _post_game("g6", "nfl", "LV", "LAC", 17, 14),
    ]})
    massey = MasseyRatingSource(espn=espn)
    massey.warmup("nfl", ["d1"])
    elo_source = EloSource(SpyEloModel({"KC": 1575.0, "DEN": 1500.0}))

    result = consensus_margin("KC", "DEN", "nfl", [massey, elo_source])

    assert result is not None
    assert abs(result.ensemble_margin) < 30.0  # sane single/low-double-digit margin
    for implied in result.per_source.values():
        assert abs(implied) < 100.0


# ---------------------------------------------------------------------------
# 5. Fail-closed
# ---------------------------------------------------------------------------


def test_massey_source_unwarmed_league_returns_none():
    source = MasseyRatingSource(espn=FakeEspnClient({}))
    assert source.rating("nfl", "KC") is None
    assert source.points_per_unit("nfl") is None


def test_colley_source_unwarmed_league_returns_none():
    source = ColleyRatingSource(espn=FakeEspnClient({}))
    assert source.rating("nfl", "KC") is None


def test_massey_source_team_below_min_games_returns_none():
    # KC plays only 1 game (< MIN_GAMES_PER_TEAM); DEN plays 3.
    espn = FakeEspnClient({("nfl", "d1"): [
        _post_game("g1", "nfl", "KC", "DEN", 20, 17),
        _post_game("g2", "nfl", "DEN", "LV", 24, 20),
        _post_game("g3", "nfl", "DEN", "LAC", 27, 21),
    ]})
    source = MasseyRatingSource(espn=espn)
    source.warmup("nfl", ["d1"])

    assert MIN_GAMES_PER_TEAM == 3
    assert source.rating("nfl", "KC") is None  # only 1 game
    assert source.rating("nfl", "DEN") is not None  # 3 games


def test_colley_source_team_below_min_games_returns_none():
    espn = FakeEspnClient({("nfl", "d1"): [
        _post_game("g1", "nfl", "KC", "DEN", 20, 17),
        _post_game("g2", "nfl", "DEN", "LV", 24, 20),
        _post_game("g3", "nfl", "DEN", "LAC", 27, 21),
    ]})
    source = ColleyRatingSource(espn=espn)
    source.warmup("nfl", ["d1"])

    assert source.rating("nfl", "KC") is None
    assert source.rating("nfl", "DEN") is not None


def test_massey_source_unsupported_league_points_per_unit_drops_source():
    espn = FakeEspnClient({("xfl", "d1"): [_post_game("g1", "xfl", "A", "B", 20, 10)]})
    source = MasseyRatingSource(espn=espn)
    source.warmup("xfl", ["d1"])

    assert source.points_per_unit("nfl") is None  # never warmed for nfl


def test_colley_source_unsupported_league_points_per_unit_is_none():
    source = ColleyRatingSource(espn=FakeEspnClient({}))
    assert source.points_per_unit("cfl") is None  # not in COLLEY_POINTS_PER_UNIT


def test_massey_source_never_calls_update_on_anything():
    # MasseyRatingSource has no model with .update() to call in the first
    # place -- this pins that its only espn interaction is `.games()`.
    espn = FakeEspnClient({("nfl", "d1"): [_post_game("g1", "nfl", "A", "B", 20, 10)]})
    source = MasseyRatingSource(espn=espn)
    source.warmup("nfl", ["d1"])

    assert not hasattr(espn, "update")
    assert espn.calls == [("nfl", "d1")]


# ---------------------------------------------------------------------------
# 6. Point-in-time: live/pre games ignored
# ---------------------------------------------------------------------------


def test_settled_results_ignores_live_and_pre_games():
    games = [
        Game("g1", "nfl", "A", "B", "pre", None, "2026-01-01"),
        Game("g2", "nfl", "A", "C", "in", None, "2026-01-01", home_score=10, away_score=7),
        _post_game("g3", "nfl", "A", "D", 20, 10),
    ]

    results = settled_results(games, "nfl")

    assert len(results) == 1
    assert results[0][:2] == ("A", "D")


def test_massey_source_warmup_ignores_live_pre_games_in_the_mix():
    espn = FakeEspnClient({("nfl", "d1"): [
        Game("g1", "nfl", "A", "B", "pre", None, "2026-01-01"),
        Game("g2", "nfl", "A", "C", "in", None, "2026-01-01", home_score=99, away_score=1),
        _post_game("g3", "nfl", "A", "B", 20, 10),
        _post_game("g4", "nfl", "B", "C", 15, 10),
        _post_game("g5", "nfl", "A", "C", 25, 10),
        _post_game("g6", "nfl", "A", "D", 20, 10),
    ]})
    source = MasseyRatingSource(espn=espn)
    source.warmup("nfl", ["d1"])

    # The live game (A beat C by 98 in-progress) must not have leaked into
    # the solve -- if it had, A's rating would be wildly inflated.
    assert source.rating("nfl", "A") is not None
    assert source.rating("nfl", "A") < 50.0


# ---------------------------------------------------------------------------
# 7. No-scraping / feed discipline: only espn.games() is ever called;
#    offline (empty games) fails closed to None.
# ---------------------------------------------------------------------------


def test_massey_source_only_calls_injected_espn_games():
    espn = FakeEspnClient({("nfl", "d1"): [_post_game("g1", "nfl", "A", "B", 20, 10)]})
    source = MasseyRatingSource(espn=espn)
    source.warmup("nfl", ["d1"])

    assert espn.calls == [("nfl", "d1")]  # no other host/method touched


def test_massey_source_offline_empty_games_fails_closed():
    espn = FakeEspnClient({})  # every query returns []
    source = MasseyRatingSource(espn=espn)
    source.warmup("nfl", ["d1", "d2"])

    assert source.rating("nfl", "KC") is None
    assert source.points_per_unit("nfl") == 1.0  # league IS "supported" (warmed), just empty
    assert source.rating("nfl", "ANY_TEAM") is None  # still fail-closed regardless


def test_colley_source_offline_empty_games_fails_closed():
    espn = FakeEspnClient({})
    source = ColleyRatingSource(espn=espn)
    source.warmup("nfl", ["d1"])

    assert source.rating("nfl", "KC") is None


# ---------------------------------------------------------------------------
# 8. Convergence at college scale (WS-A1b review fix): a ~360-team system
#    (NCAAF/NCAAMB scale) is only weakly diagonally dominant -- the old
#    _MAX_ITER=2000/_TOL=1e-9 budget could exhaust before reaching tol,
#    silently returning None and dropping the whole league from the
#    ensemble. Build a large, fully deterministic (no RNG/datetime) schedule
#    and assert both solves still converge.
# ---------------------------------------------------------------------------


def _deterministic_large_schedule(n_teams: int = 360, offsets: tuple[int, ...] = (
    1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31,
)) -> list[tuple[str, str, float, bool]]:
    """~360 teams, each scheduled against `len(offsets)` opponents chosen by
    deterministic index arithmetic (opponent = (i + offset) % n) -- no RNG,
    no datetime, byte-identical across runs. Home/away alternates by offset
    parity and scores are a deterministic function of (team indices, offset
    index) so margins vary realistically without any randomness source."""
    teams = [f"T{i:03d}" for i in range(n_teams)]
    results: list[tuple[str, str, float, bool]] = []
    for i in range(n_teams):
        for idx, off in enumerate(offsets):
            j = (i + off) % n_teams
            home_score = 60 + ((i * 13 + off * 7 + idx * 3) % 40)
            away_score = 60 + ((j * 11 + off * 5 + idx * 2) % 40)
            if home_score == away_score:
                home_score += 1
            if idx % 2 == 0:
                home, away, hs, as_ = teams[i], teams[j], home_score, away_score
            else:
                home, away, hs, as_ = teams[j], teams[i], away_score, home_score
            results.append((home, away, float(hs - as_), hs > as_))
    return results


def test_solve_massey_converges_at_college_scale():
    results = _deterministic_large_schedule()
    teams = sorted({t for h, a, _, _ in results for t in (h, a)})
    assert len(teams) == 360

    ratings, games_played = solve_massey(results)

    assert ratings is not None
    assert set(ratings) == set(teams)
    assert all(games_played[t] >= MIN_GAMES_PER_TEAM for t in teams)
    # Ridge-regularized Massey ratings cluster near zero-sum (small ridge
    # pull toward zero, not an exact sum-to-zero constraint).
    assert abs(sum(ratings.values())) < len(teams) * 5.0


def test_solve_colley_converges_at_college_scale():
    results = _deterministic_large_schedule()
    teams = sorted({t for h, a, _, _ in results for t in (h, a)})
    assert len(teams) == 360

    ratings, games_played = solve_colley(results)

    assert ratings is not None
    assert set(ratings) == set(teams)
    assert all(games_played[t] >= MIN_GAMES_PER_TEAM for t in teams)
    # Colley ratings are dimensionless, centered at 0.5, summing to n/2.
    assert sum(ratings.values()) == pytest.approx(len(teams) / 2.0, abs=1e-3)
    assert all(0.0 <= r <= 1.0 for r in ratings.values())
