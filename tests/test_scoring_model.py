"""Phase 2: expected margin/total scoring model + walk-forward."""
from __future__ import annotations

from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.scoring_model import LakeScoringModel
from autonomy.sports.walk_forward import walk_forward_scoring


def _game(gid, start, home, away, hs, as_):
    return {"game_id": gid, "league": "nba", "season": 2025, "start_time": start,
            "home": home, "away": away, "home_score": hs, "away_score": as_,
            "status": "final", "source": "t"}


def _seed(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    day = 1
    for wk in range(12):
        st.upsert_game(_game(f"a{wk}", f"2025-01-{day:02d}T00:00:00Z", "AAA", "CCC", 118, 95)); day += 1
        st.upsert_game(_game(f"b{wk}", f"2025-01-{day:02d}T00:00:00Z", "BBB", "CCC", 104, 99)); day += 1
        st.upsert_game(_game(f"c{wk}", f"2025-01-{day:02d}T00:00:00Z", "AAA", "BBB", 110, 101)); day += 1
    return st


def test_expected_margin_total_and_probs(tmp_path):
    st = _seed(tmp_path)
    m = LakeScoringModel(st, league="nba")
    t = "2025-03-01T00:00:00Z"
    assert m.expected_margin("AAA", "CCC", t) > 0        # AAA outscores CCC
    tot = m.expected_total("AAA", "CCC", t)
    assert 150 < tot < 260                                # sane basketball total
    assert m.p_home_covers("AAA", "CCC", t, 0.0) > 0.5
    assert 0 < m.p_over("AAA", "CCC", t, tot - 5) < 1 and m.p_over("AAA", "CCC", t, tot - 5) > 0.5
    st.close()


def test_walk_forward_scoring(tmp_path):
    st = _seed(tmp_path)
    r = walk_forward_scoring(st, league="nba", min_games=2)
    assert r["n"] > 8 and r["hit_rate"] > 0.6
    assert r["margin_mae"] is not None and r["total_mae"] is not None
    st.close()
