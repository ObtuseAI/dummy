"""Phase 2: Glicko-2 rating engine + lake-backed point-in-time ratings.

The engine is checked against Glickman's own worked example (the canonical
Glicko-2 paper) so the math is exact, not just plausible.
"""
from __future__ import annotations

from autonomy.sports.glicko import Glicko2, LakeGlickoRatings
from autonomy.sports.history_store import SportsHistoryStore


def test_matches_glickman_worked_example():
    # Paper: player 1500/200/0.06, tau=0.5, vs 1400/30 (win), 1550/100 (loss),
    # 1700/300 (loss) -> r'~1464.06, RD'~151.52, vol'~0.05999.
    g = Glicko2(tau=0.5)
    r, rd, vol = g.update(
        1500.0, 200.0, 0.06,
        [(1400.0, 30.0, 1.0), (1550.0, 100.0, 0.0), (1700.0, 300.0, 0.0)],
    )
    assert abs(r - 1464.06) < 0.1
    assert abs(rd - 151.52) < 0.2
    assert abs(vol - 0.05999) < 0.0001


def test_no_games_only_inflates_rd():
    g = Glicko2()
    r, rd, vol = g.update(1500.0, 200.0, 0.06, [])
    assert abs(r - 1500.0) < 1e-9          # rating unchanged with no games
    assert rd >= 200.0                     # uncertainty grows while idle


def test_expected_score_favours_the_higher_rating():
    g = Glicko2()
    assert g.expected_score(1700, 50, 1500, 50) > 0.5
    assert abs(g.expected_score(1500, 50, 1500, 50) - 0.5) < 1e-6


def _game(gid, start, home, away, hs, as_, status="final"):
    return {"game_id": gid, "league": "nfl", "season": 2025, "start_time": start,
            "home": home, "away": away, "home_score": hs, "away_score": as_,
            "status": status, "source": "test"}


def test_lake_ratings_are_point_in_time_and_sensible(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    # AAA beats BBB three times before the cutoff; a 4th game is unplayed.
    st.upsert_game(_game("g1", "2025-09-01T00:00:00Z", "AAA", "BBB", 30, 10))
    st.upsert_game(_game("g2", "2025-09-08T00:00:00Z", "BBB", "AAA", 10, 27))
    st.upsert_game(_game("g3", "2025-09-15T00:00:00Z", "AAA", "BBB", 24, 20))
    st.upsert_game(_game("g4", "2025-09-22T00:00:00Z", "AAA", "BBB", None, None, status="scheduled"))

    ratings = LakeGlickoRatings(st, league="nfl")
    ratings.warm("2025-09-20T00:00:00Z")           # only g1..g3 are visible
    assert ratings.rating("AAA") > ratings.rating("BBB")
    p = ratings.matchup_prob("AAA", "BBB")
    assert 0.5 < p < 1.0
    # symmetric
    assert abs(ratings.matchup_prob("BBB", "AAA", home_advantage=0.0)
               + ratings.matchup_prob("AAA", "BBB", home_advantage=0.0) - 1.0) < 1e-6
    # a team never seen is at the default rating
    assert abs(ratings.rating("ZZZ") - 1500.0) < 1e-9
    st.close()
