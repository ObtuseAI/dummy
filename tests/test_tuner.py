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
        if best.get("skipped"):
            # Fail-closed sign gate: an edge<=0 grid winner is recorded for
            # audit but never carries a live value.
            assert best["skipped"] == "edge<=0" and best["value"] is None
            continue
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


def test_negative_edge_winner_not_persisted_but_audited(tmp_path, monkeypatch):
    # 2026-07-24 audit: the tuner persisted mlb glicko/mov_elo with NEGATIVE
    # edge (a refit measurably worse than baseline, applied live). The grid
    # maximum must be sign-gated: edge<=0 -> value-less skip record in the
    # artifact, live signals keep the reviewable prior via load_tuned.
    import autonomy.sports.tuner as tuner
    import autonomy.sports.walk_forward as wf

    def negative(store, league, home_advantage=35.0):
        return {"n": 500, "hit_rate": 0.52, "edge_vs_baseline": -0.003}

    def positive(store, league, home_advantage=35.0):
        return {"n": 500, "hit_rate": 0.56,
                "edge_vs_baseline": 0.004 + home_advantage / 1e5}

    def absent(store, league, **_kw):
        return {"n": 0}

    monkeypatch.setattr(wf, "walk_forward_glicko", negative)
    monkeypatch.setattr(wf, "walk_forward_mov_elo", positive)
    monkeypatch.setattr(wf, "walk_forward_pythagorean", absent)
    monkeypatch.setattr(wf, "walk_forward_four_factors", absent)
    monkeypatch.setattr(wf, "walk_forward_rest", absent)
    monkeypatch.setattr(tuner, "tune_scoring_sigmas", lambda store, lg: {})

    p = tmp_path / "tuned.json"
    tuner.tune_all(None, ["mlb"], path=p)
    import json

    blob = json.loads(p.read_text(encoding="utf-8"))
    glicko = blob["leagues"]["mlb"]["glicko"]
    # Negative-edge winner: audited skip, no live value.
    assert glicko["skipped"] == "edge<=0"
    assert glicko["value"] is None
    assert glicko["edge"] == -0.003
    assert glicko["rejected_value"] == 20.0
    assert load_tuned("mlb", "glicko", "home_advantage", 24.0, path=p) == 24.0
    # Positive-edge winner: persisted and consumed exactly as before.
    mov = blob["leagues"]["mlb"]["mov_elo"]
    assert "skipped" not in mov and mov["value"] == 60.0 and mov["edge"] > 0.0
    assert load_tuned("mlb", "mov_elo", "home_advantage", 24.0, path=p) == 60.0


def test_zero_edge_winner_rejected():
    # Boundary: edge == 0 is "no better than baseline" -> also rejected.
    from autonomy.sports.tuner import tune_param

    def wf_zero(store, league, coefficient=0.0):
        return {"n": 100, "hit_rate": 0.5, "edge_vs_baseline": 0.0}

    best = tune_param(None, "mlb", wf_zero, "coefficient", [0.0, 0.03])
    assert best["value"] is None
    assert best["skipped"] == "edge<=0"
    assert best["edge"] == 0.0


def test_tune_all_persists_incrementally_and_preserves_prior(tmp_path, monkeypatch):
    # A run cut short (task time limit) must still land the leagues it finished,
    # and must not wipe leagues from a prior run that it did not reach.
    import autonomy.sports.tuner as tuner

    st = _seed(tmp_path)
    p = tmp_path / "tuned.json"
    # Seed a prior file with a league this run won't touch (wnba).
    tuner._write_tuned(p, {"wnba": {"glicko": {"param": "home_advantage",
                                               "value": 33.0, "n": 5}}})
    # Simulate termination: nfl tunes, then the next league raises.
    real = tuner.tune_league
    calls = {"n": 0}

    def flaky(store, lg):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise KeyboardInterrupt("simulated task-timeout kill")
        return real(store, lg)

    monkeypatch.setattr(tuner, "tune_league", flaky)
    try:
        tuner.tune_all(st, ["nfl", "mlb"], path=p)
    except KeyboardInterrupt:
        pass
    # nfl (finished before the kill) persisted; wnba (prior, untouched) preserved.
    assert load_tuned("nfl", "glicko", "home_advantage", 0.0, path=p) > 0.0
    assert load_tuned("wnba", "glicko", "home_advantage", 0.0, path=p) == 33.0
    st.close()


def test_tune_all_tunes_least_recently_tuned_first(tmp_path, monkeypatch):
    """Wave-85: a fixed league order starves the tail forever.

    tune_all persisting per-league (Wave-84) stopped the data loss but not the
    starvation: DummyTune was still killed at its PT1H limit, so with a fixed
    caller order the same leading leagues were re-tuned every run and the tail
    was never tuned even once. The live artifact showed exactly that -- tuned
    values for nfl/wnba/mlb and nothing at all for nba/ncaamb/ncaaf/nhl.

    Least-recently-tuned goes first, so every league eventually gets its turn.
    """
    import autonomy.sports.tuner as tuner

    st = _seed(tmp_path)
    p = tmp_path / "tuned.json"
    order: list[str] = []

    real = tuner.tune_league
    monkeypatch.setattr(
        tuner, "tune_league",
        lambda store, lg: (order.append(lg), real(store, lg))[1],
    )

    leagues = ["nfl", "mlb"]
    tuner.tune_all(st, leagues, path=p)
    first_pass = list(order)
    assert set(first_pass) == {"nfl", "mlb"}

    # Second pass: the league tuned FIRST last time is now the stalest, so it
    # must come last -- i.e. the order flips rather than repeating.
    order.clear()
    tuner.tune_all(st, leagues, path=p)
    assert order == list(reversed(first_pass)), (first_pass, order)
    st.close()


def test_tune_all_budget_stops_cleanly_without_losing_progress(tmp_path, monkeypatch):
    """An exhausted budget must end the run, not raise and not wipe progress."""
    import autonomy.sports.tuner as tuner

    st = _seed(tmp_path)
    p = tmp_path / "tuned.json"
    tuner.tune_all(st, ["nfl"], path=p)          # nfl tuned and stamped
    before = load_tuned("nfl", "glicko", "home_advantage", 0.0, path=p)
    assert before > 0.0

    # A budget already spent means no league is attempted at all this run.
    called: list[str] = []
    monkeypatch.setattr(
        tuner, "tune_league",
        lambda store, lg: called.append(lg) or {},
    )
    tuner.tune_all(st, ["mlb", "nfl"], path=p, budget_s=-1.0)
    assert called == []
    # Prior progress survives untouched.
    assert load_tuned("nfl", "glicko", "home_advantage", 0.0, path=p) == before
    st.close()
