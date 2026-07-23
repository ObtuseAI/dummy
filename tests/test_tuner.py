"""Phase 4: analytic hyperparameter self-tuner."""
from __future__ import annotations

from autonomy.sports.history_store import SportsHistoryStore
from autonomy.sports.tuner import load_tuned, tune_all, tune_league


def _seed(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    day = 1
    for wk in range(40):
        for gid, h, a, hs, as_ in ((f"a{wk}", "AAA", "BBB", 30, 10), (f"b{wk}", "AAA", "CCC", 27, 20)):
            start = f"2025-{(day // 28) + 1:02d}-{(day % 28) + 1:02d}"
            st.upsert_game({"game_id": gid, "league": "nfl", "season": 2025,
                            "start_time": f"{start}T00:00:00Z",
                            "home": h, "away": a, "home_score": hs, "away_score": as_,
                            "status": "final", "source": "t",
                            "result_available_at": f"{start}T03:00:00Z",
                            "received_at": f"{start}T03:05:00Z",
                            "provenance_quality": "source_reported"})
            day += 1
    return st


def test_tune_league_and_persist(tmp_path):
    st = _seed(tmp_path)
    tuned = tune_league(st, "nfl")
    assert "glicko" in tuned and "mov_elo" in tuned
    home_grids = (20.0, 30.0, 40.0, 50.0, 60.0, 0.0, 0.02, 0.04, 0.06, 0.08)
    for name, best in tuned.items():
        if name.startswith("scoring_sigma"):
            # Wave-62: sigmas tune on out-of-sample likelihood over a
            # multiplier grid around the league prior, not the home grids.
            assert best["objective"] == "mean_normal_loglik"
            assert best["value"] > 0.0
        else:
            assert best["value"] in home_grids
        assert best["n"] > 0

    p = tmp_path / "tuned.json"
    tune_all(st, ["nfl"], path=p)
    # load_tuned returns the persisted value, or the default on any miss
    v = load_tuned("nfl", "glicko", "home_advantage", 40.0, path=p)
    assert v == tuned["glicko"]["value"]
    assert load_tuned("nfl", "nope", "x", 99.0, path=p) == 99.0
    assert load_tuned("mlb", "glicko", "home_advantage", 24.0, path=tmp_path / "absent.json") == 24.0
    st.close()
