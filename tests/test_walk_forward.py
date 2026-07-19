"""Phase 4: walk-forward point-in-time evaluation of a rating analytic.

Predict each game BEFORE it is played (using only prior games), grade against
the actual result. This is the honest measure of an analytic's edge and the
signal the recursive tuner acts on.
"""
from __future__ import annotations

from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.walk_forward import walk_forward_glicko


def _game(gid, start, home, away, hs, as_):
    return {"game_id": gid, "league": "nfl", "season": 2025, "start_time": start,
            "home": home, "away": away, "home_score": hs, "away_score": as_,
            "status": "final", "source": "test"}


def test_walk_forward_grades_a_predictable_league(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    # A strict hierarchy AAA > BBB > CCC, each pairing repeated across weeks.
    day = 1
    for week in range(8):
        st.upsert_game(_game(f"a{week}", f"2025-09-{day:02d}T00:00:00Z", "AAA", "BBB", 30, 10)); day += 1
        st.upsert_game(_game(f"b{week}", f"2025-09-{day:02d}T00:00:00Z", "BBB", "CCC", 24, 17)); day += 1
        st.upsert_game(_game(f"c{week}", f"2025-09-{day:02d}T00:00:00Z", "AAA", "CCC", 35, 14)); day += 1

    report = walk_forward_glicko(st, league="nfl")
    assert report["n"] > 12
    # Once ratings warm up, the model beats a coin flip decisively.
    assert report["brier"] < 0.25                 # better than always-0.5 (0.25)
    assert report["hit_rate"] > 0.7
    assert report["baseline_brier"] == 0.25
    assert report["edge_vs_baseline"] > 0         # brier improvement over 0.5
    st.close()


def test_walk_forward_empty_is_safe(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    report = walk_forward_glicko(st, league="nfl")
    assert report["n"] == 0 and report["brier"] is None
    st.close()
