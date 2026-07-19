"""Phase 2: Pythagenpat strength engine + lake walk-forward."""
from __future__ import annotations

from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.pythagorean import LakePythagorean, log5, win_expectation
from autonomy.sports.walk_forward import walk_forward_pythagorean


def test_win_expectation_rewards_outscoring():
    # Outscored opponents 2:1 over a season -> strong; even -> 0.5.
    assert win_expectation(500, 250, 82) > 0.7
    assert abs(win_expectation(300, 300, 82) - 0.5) < 1e-9
    # log5 of two even teams is a coin flip; a strong vs weak team is favored
    assert abs(log5(0.5, 0.5) - 0.5) < 1e-9
    assert log5(0.7, 0.4) > 0.5


def _game(gid, start, home, away, hs, as_):
    return {"game_id": gid, "league": "nfl", "season": 2025, "start_time": start,
            "home": home, "away": away, "home_score": hs, "away_score": as_,
            "status": "final", "source": "t"}


def test_lake_strength_is_point_in_time(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    st.upsert_game(_game("g1", "2025-09-01T00:00:00Z", "AAA", "BBB", 40, 10))
    st.upsert_game(_game("g2", "2025-09-08T00:00:00Z", "AAA", "BBB", 35, 14))
    st.upsert_game(_game("g3", "2025-09-15T00:00:00Z", "AAA", "BBB", None, None))  # unplayed
    p = LakePythagorean(st, league="nfl").warm("2025-09-20T00:00:00Z")
    assert p.strength("AAA") > 0.7 and p.strength("BBB") < 0.3
    assert p.matchup_prob("AAA", "BBB") > 0.5
    assert p.games_seen("AAA") == 2                 # the unplayed game is invisible
    st.close()


def test_walk_forward_pythagorean_beats_coin_on_a_hierarchy(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    day = 1
    for week in range(10):
        st.upsert_game(_game(f"a{week}", f"2025-09-{day:02d}T00:00:00Z", "AAA", "CCC", 35, 10)); day += 1
        st.upsert_game(_game(f"b{week}", f"2025-09-{day:02d}T00:00:00Z", "BBB", "CCC", 27, 20)); day += 1
        st.upsert_game(_game(f"c{week}", f"2025-09-{day:02d}T00:00:00Z", "AAA", "BBB", 30, 24)); day += 1
    r = walk_forward_pythagorean(st, league="nfl")
    assert r["n"] > 10 and r["brier"] < 0.25 and r["hit_rate"] > 0.6
    st.close()
