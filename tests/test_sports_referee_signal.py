"""Referee tendency model, bounded backfill, and totals challenger."""
from __future__ import annotations


from autonomy.sports.referees import (
    MIN_REFEREE_GAMES,
    RefereeTendencies,
    parse_officials,
    summary_total,
)


def test_parse_officials_and_total():
    summary = {
        "gameInfo": {"officials": [
            {"fullName": "Josh Tiven"}, {"displayName": "Matt Kallio"}, {},
        ]},
        "header": {"competitions": [{"competitors": [
            {"score": "112"}, {"score": "108"},
        ]}]},
    }
    assert parse_officials(summary) == ["Josh Tiven", "Matt Kallio"]
    assert summary_total(summary) == 220
    assert summary_total({"header": {"competitions": [{"competitors": [{"score": "x"}]}]}}) is None


def test_tendencies_gate_on_min_games_and_crew_delta(tmp_path):
    path = tmp_path / "ref.json"
    tend = RefereeTendencies(path)
    # An over-leaning ref: every game totals 240 while the league averages ~215.
    for _ in range(MIN_REFEREE_GAMES):
        tend.observe("nba", ["Over Ref"], 240)
    for _ in range(MIN_REFEREE_GAMES):
        tend.observe("nba", ["Under Ref"], 195)
    tend.save()

    reloaded = RefereeTendencies(path)
    assert reloaded.league_mean_total("nba") == 217.5
    over = reloaded.crew_total_delta("nba", ["Over Ref"])
    assert over["delta"] > 0 and "Over Ref" in over["qualified_referees"]
    under = reloaded.crew_total_delta("nba", ["Under Ref"])
    assert under["delta"] < 0
    # A referee below the min-games gate is not qualified -> no delta.
    thin = RefereeTendencies(tmp_path / "thin.json")
    thin.observe("nba", ["Rookie"], 240)
    assert thin.crew_total_delta("nba", ["Rookie"]) is None


def test_crew_delta_is_clamped(tmp_path):
    tend = RefereeTendencies(tmp_path / "c.json")
    for _ in range(MIN_REFEREE_GAMES):
        tend.observe("mlb", ["Wild Ump"], 40)   # absurd run total
    for _ in range(MIN_REFEREE_GAMES):
        tend.observe("mlb", ["Normal Ump"], 8)
    delta = tend.crew_total_delta("mlb", ["Wild Ump"])
    assert abs(delta["delta"]) <= 1.2 + 1e-9   # MLB cap
    assert delta["raw_delta"] > delta["delta"]  # raw exceeds the clamp


def test_backfill_folds_officials_from_summaries(tmp_path):
    from autonomy.ingest.referee_lake import backfill_referees

    class _Store:
        def evaluation_games(self, league=None):
            return [{"game_id": f"40100{i}"} for i in range(3)]

    def fake_fetch(url):
        return {
            "gameInfo": {"officials": [{"fullName": "Ref A"}, {"fullName": "Ref B"}]},
            "header": {"competitions": [{"competitors": [{"score": "110"}, {"score": "105"}]}]},
        }

    tend = RefereeTendencies(tmp_path / "t.json")
    report = backfill_referees(
        _Store(), "nba", tendencies=tend, max_games=2, fetch_json=fake_fetch,
    )
    assert report["games_processed"] == 2
    assert report["referee_observations"] == 4  # 2 games x 2 refs
    assert report["league_mean_total"] == 215.0


def test_backfill_skips_games_without_officials_or_total(tmp_path):
    from autonomy.ingest.referee_lake import backfill_referees

    class _Store:
        def evaluation_games(self, league=None):
            return [{"game_id": "401001"}, {"game_id": "401002"}]

    calls = {"n": 0}

    def fake_fetch(url):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"gameInfo": {"officials": []}, "header": {}}   # no officials
        return {
            "gameInfo": {"officials": [{"fullName": "Ref A"}]},
            "header": {"competitions": [{"competitors": [{"score": "100"}, {"score": "99"}]}]},
        }

    report = backfill_referees(
        _Store(), "nba", tendencies=RefereeTendencies(tmp_path / "t.json"),
        fetch_json=fake_fetch,
    )
    assert report["games_processed"] == 2
    assert report["skipped"] == 1
    assert report["referee_observations"] == 1
