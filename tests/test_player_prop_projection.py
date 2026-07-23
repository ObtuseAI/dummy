"""Player prop projection model, parser, game-log accessor, and challenger."""
from __future__ import annotations

from autonomy.sports.boxscores import parse_player_boxscores
from autonomy.sports.player_props import (
    project_minutes,
    project_stat,
    prop_over_probability,
)


def _log(n, minutes, points):
    return [{"minutes": minutes, "points": points, "rebounds": 8} for _ in range(n)]


def test_project_minutes_needs_min_games():
    assert project_minutes([34, 33, 35]) is None       # < MIN_GAMES
    assert project_minutes([34, 33, 35, 36, 34]) is not None


def test_project_stat_mean_and_dispersion():
    proj = project_stat(_log(10, 32.0, 24.0), "points")
    assert proj is not None
    assert abs(proj["mean"] - 24.0) < 1e-6
    assert proj["sigma"] > 0
    assert proj["games"] == 10
    assert project_stat([{"minutes": 0, "points": 5}] * 10, "points") is None


def test_recency_weighting_favours_recent_games():
    # 3 recent high games + 7 older low games. Flat-count mean is 16; recency
    # weighting must lift the projection above that (recent games lead) while
    # the low majority keeps it below the recent value.
    log = [{"minutes": 32, "points": 30}] * 3 + [{"minutes": 32, "points": 10}] * 7
    proj = project_stat(log, "points")
    assert 16.0 < proj["mean"] < 30.0


def test_prop_over_probability_continuity_and_direction():
    p = prop_over_probability(24.0, 5.0, 20)
    assert 0.5 < p < 1.0
    assert prop_over_probability(18.0, 5.0, 24) < 0.5
    assert prop_over_probability(24.0, 0.0, 20) is None


def test_parse_player_boxscores_from_espn_summary():
    summary = {
        "header": {"id": "401585000"},
        "boxscore": {"players": [{
            "team": {"abbreviation": "LAC"},
            "statistics": [{
                "labels": ["MIN", "PTS", "3PT", "REB", "AST"],
                "athletes": [
                    {"athlete": {"displayName": "Kawhi Leonard"},
                     "stats": ["37", "30", "1-6", "10", "5"]},
                    {"athlete": {"displayName": "James Harden"},
                     "stats": ["35", "20", "3-8", "4", "9"]},
                ],
            }],
        }]},
    }
    rows = parse_player_boxscores("nba", summary)
    by = {(r["player"], r["stat"]): r["value"] for r in rows}
    assert by[("Kawhi Leonard", "minutes")] == 37.0
    assert by[("Kawhi Leonard", "points")] == 30.0
    assert by[("Kawhi Leonard", "threes")] == 1.0     # made count from "1-6"
    assert by[("James Harden", "assists")] == 9.0
    assert parse_player_boxscores("nfl", summary) == []


def test_player_game_log_pivots_stats_point_in_time(tmp_path):
    from autonomy.sports.history_store import SportsHistoryStore

    store = SportsHistoryStore(tmp_path / "lake.db")
    store.upsert_games([
        {"game_id": "g1", "league": "nba", "start_time": "2026-01-05T00:00:00Z",
         "status": "final", "home": "LAC", "away": "BOS", "home_score": 110, "away_score": 100},
        {"game_id": "g2", "league": "nba", "start_time": "2026-01-08T00:00:00Z",
         "status": "final", "home": "LAC", "away": "NYK", "home_score": 105, "away_score": 99},
    ])
    store.record_player_boxscores([
        {"game_id": "g1", "team": "LAC", "player": "Kawhi Leonard", "stat": "minutes", "value": 34},
        {"game_id": "g1", "team": "LAC", "player": "Kawhi Leonard", "stat": "points", "value": 28},
        {"game_id": "g2", "team": "LAC", "player": "Kawhi Leonard", "stat": "minutes", "value": 36},
        {"game_id": "g2", "team": "LAC", "player": "Kawhi Leonard", "stat": "points", "value": 31},
    ])
    log = store.player_game_log("Kawhi Leonard", "2026-01-10T00:00:00Z", league="nba")
    assert [e["game_id"] for e in log] == ["g2", "g1"]
    assert log[0]["points"] == 31.0 and log[0]["minutes"] == 36.0
    log2 = store.player_game_log("Kawhi Leonard", "2026-01-06T00:00:00Z", league="nba")
    assert [e["game_id"] for e in log2] == ["g1"]
