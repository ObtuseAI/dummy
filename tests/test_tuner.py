"""Phase 4: analytic hyperparameter self-tuner."""
from __future__ import annotations

from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.tuner import load_tuned, tune_all, tune_league


def _seed(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    day = 1
    for wk in range(40):
        for gid, h, a, hs, as_ in ((f"a{wk}", "AAA", "BBB", 30, 10), (f"b{wk}", "AAA", "CCC", 27, 20)):
            st.upsert_game({"game_id": gid, "league": "nfl", "season": 2025,
                            "start_time": f"2025-{(day // 28) + 1:02d}-{(day % 28) + 1:02d}T00:00:00Z",
                            "home": h, "away": a, "home_score": hs, "away_score": as_,
                            "status": "final", "source": "t"})
            day += 1
    return st


def test_tune_league_and_persist(tmp_path):
    st = _seed(tmp_path)
    tuned = tune_league(st, "nfl")
    assert "glicko" in tuned and "mov_elo" in tuned
    for name, best in tuned.items():
        assert best["value"] in (20.0, 30.0, 40.0, 50.0, 60.0, 0.0, 0.02, 0.04, 0.06, 0.08)
        assert best["n"] > 0

    p = tmp_path / "tuned.json"
    tune_all(st, ["nfl"], path=p)
    # load_tuned returns the persisted value, or the default on any miss
    v = load_tuned("nfl", "glicko", "home_advantage", 40.0, path=p)
    assert v == tuned["glicko"]["value"]
    assert load_tuned("nfl", "nope", "x", 99.0, path=p) == 99.0
    assert load_tuned("mlb", "glicko", "home_advantage", 24.0, path=tmp_path / "absent.json") == 24.0
    st.close()
