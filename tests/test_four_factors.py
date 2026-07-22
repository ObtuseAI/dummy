"""Phase 2: Four Factors engine + point-in-time lake aggregation + walk-forward."""
from __future__ import annotations

from autonomy.sports.four_factors import LakeFourFactors, four_factors, net_rating
from autonomy.sports.history_store import SportsHistoryStore

# good shooting team vs poor one
_GOOD = {"fieldGoalsMade": 45, "fieldGoalsAttempted": 85, "threePointFieldGoalsMade": 12,
         "freeThrowsMade": 18, "freeThrowsAttempted": 22, "offensiveRebounds": 12, "turnovers": 10}
_POOR = {"fieldGoalsMade": 33, "fieldGoalsAttempted": 85, "threePointFieldGoalsMade": 7,
         "freeThrowsMade": 12, "freeThrowsAttempted": 18, "offensiveRebounds": 7, "turnovers": 17}


def test_four_factors_math():
    ff = four_factors(_GOOD)
    assert abs(ff["efg"] - (45 + 0.5 * 12) / 85) < 1e-9
    assert 0 < ff["tov"] < 0.3 and 0 < ff["orb"] < 1 and 0 < ff["ftr"] < 1
    assert net_rating(four_factors(_GOOD), four_factors(_POOR)) > 0
    assert four_factors({"fieldGoalsAttempted": 0}) is None


def _game(gid, start, home, away, hs, as_):
    return {"game_id": gid, "league": "wnba", "season": 2025, "start_time": start,
            "home": home, "away": away, "home_score": hs, "away_score": as_,
            "status": "final", "source": "t",
            "result_available_at": start.replace("T00:00:00Z", "T03:00:00Z"),
            "received_at": start.replace("T00:00:00Z", "T03:05:00Z"),
            "provenance_quality": "source_reported"}


def _seed(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    day = 1
    for wk in range(10):
        gid = f"g{wk}"
        st.upsert_game(_game(gid, f"2025-06-{day:02d}T00:00:00Z", "AAA", "BBB", 88, 74))
        st.record_team_boxscores([
            {"game_id": gid, "team": "AAA", "stats": _GOOD},
            {"game_id": gid, "team": "BBB", "stats": _POOR},
        ])
        day += 1
    return st


def test_point_in_time_sums_and_strength(tmp_path):
    st = _seed(tmp_path)
    m = LakeFourFactors(st, league="wnba")
    # AAA's offense = its own shooting; defense = what BBB did against it
    assert m.strength("AAA", "2025-07-01T00:00:00Z") > m.strength("BBB", "2025-07-01T00:00:00Z")
    p = m.matchup_prob("AAA", "BBB", "2025-07-01T00:00:00Z")
    assert p is not None and p > 0.5
    # point-in-time: as-of before any game -> no data
    assert st.four_factor_sums_before("AAA", "2025-05-01T00:00:00Z", "wnba") is None
    st.close()


def test_walk_forward_four_factors(tmp_path):
    from autonomy.sports.walk_forward import walk_forward_four_factors
    st = _seed(tmp_path)
    r = walk_forward_four_factors(st, league="wnba", min_games=2)
    assert r["n"] > 4 and r["hit_rate"] >= 0.9      # AAA always wins + always favored
    st.close()
