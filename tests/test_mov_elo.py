"""Phase 2: margin-of-victory Elo engine + lake walk-forward."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.mov_elo import LakeMovElo, MovElo
from autonomy.sports.walk_forward import walk_forward_mov_elo


def test_bigger_margin_moves_rating_more():
    eng = MovElo(k=20.0)
    # even ratings; a 30-point win should move more than a 3-point win.
    r_big, _ = eng.update(1500, 1500, 40, 10)
    r_small, _ = eng.update(1500, 1500, 41, 38)
    assert r_big > r_small > 1500
    # expected score favours the higher rating + home edge
    assert eng.expected(1600, 1500, 40) > 0.5
    assert abs(eng.expected(1500, 1500, 0) - 0.5) < 1e-9


def _game(gid, start, home, away, hs, as_):
    return {"game_id": gid, "league": "nfl", "season": 2025, "start_time": start,
            "home": home, "away": away, "home_score": hs, "away_score": as_,
            "status": "final", "source": "t",
            "result_available_at": start.replace("T00:00:00Z", "T03:00:00Z").replace(
                "T00:00:00+00:00", "T03:00:00+00:00"),
            "received_at": start.replace("T00:00:00Z", "T03:05:00Z").replace(
                "T00:00:00+00:00", "T03:05:00+00:00"),
            "provenance_quality": "source_reported"}


def test_lake_ratings_point_in_time(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    st.upsert_game(_game("g1", "2025-09-01T00:00:00Z", "AAA", "BBB", 35, 10))
    st.upsert_game(_game("g2", "2025-09-08T00:00:00Z", "BBB", "AAA", 14, 31))
    st.upsert_game(_game("g3", "2025-09-15T00:00:00Z", "AAA", "BBB", None, None))
    m = LakeMovElo(st, league="nfl").warm("2025-09-20T00:00:00Z")
    assert m.rating("AAA") > m.rating("BBB")
    assert m.matchup_prob("AAA", "BBB") > 0.5
    st.close()


def test_walk_forward_beats_coin(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    start = datetime(2025, 9, 1, tzinfo=timezone.utc)
    day = 0
    for wk in range(16):
        st.upsert_game(_game(f"a{wk}", (start + timedelta(days=day)).isoformat(), "AAA", "CCC", 35, 12))
        day += 1
        st.upsert_game(_game(f"b{wk}", (start + timedelta(days=day)).isoformat(), "BBB", "CCC", 24, 20))
        day += 1
        st.upsert_game(_game(f"c{wk}", (start + timedelta(days=day)).isoformat(), "AAA", "BBB", 30, 21))
        day += 1
    r = walk_forward_mov_elo(st, league="nfl", warmup_games=6)
    assert r["n"] > 10 and r["brier"] < 0.25 and r["hit_rate"] > 0.6
    st.close()
