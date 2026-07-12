"""Tests for the boxscore stat pipeline (WS-1: foundation for NBA/NHL/NFL engines).

All parsing tests read committed, trimmed real ESPN fixtures captured during
the build-time probe (see autonomy/sports/boxscores.py module docstring for
event ids/dates). Zero network in this file.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonomy.sports.boxscores import BoxscoreStore, TeamBoxscore, parse_team_boxscores

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- parsing


def test_parse_nba_boxscore_from_real_fixture():
    summary = _load_fixture("boxscore_nba_401810960.json")
    boxscores = parse_team_boxscores("nba", summary)
    assert len(boxscores) == 2

    by_team = {b.team: b for b in boxscores}
    assert set(by_team) == {"PHI", "WSH"}

    phi = by_team["PHI"]
    assert phi.game_id == "401810960"
    assert phi.league == "nba"
    assert phi.opponent == "WSH"
    assert phi.is_home is False
    # ESPN packs made/attempted into one composite displayValue ("61-99");
    # the brief expected standalone `fieldGoalsAttempted` -- split it.
    assert phi.stats["fieldGoalsMade"] == 61.0
    assert phi.stats["fieldGoalsAttempted"] == 99.0
    assert phi.stats["freeThrowsMade"] == 14.0
    assert phi.stats["freeThrowsAttempted"] == 16.0
    assert phi.stats["offensiveRebounds"] == 10.0
    assert phi.stats["turnovers"] == 10.0
    # No `points` key: not present anywhere in boxscore.teams[].statistics.
    assert "points" not in phi.stats

    wsh = by_team["WSH"]
    assert wsh.opponent == "PHI"
    assert wsh.is_home is True
    assert wsh.stats["fieldGoalsAttempted"] == 96.0
    assert wsh.stats["offensiveRebounds"] == 7.0
    assert wsh.stats["turnovers"] == 11.0

    # Possessions sanity check per the brief's formula: FGA - ORB + TO + 0.44*FTA
    possessions_phi = (
        phi.stats["fieldGoalsAttempted"]
        - phi.stats["offensiveRebounds"]
        + phi.stats["turnovers"]
        + 0.44 * phi.stats["freeThrowsAttempted"]
    )
    assert possessions_phi == pytest.approx(99 - 10 + 10 + 0.44 * 16, abs=1e-9)


def test_parse_nhl_boxscore_from_real_fixture():
    summary = _load_fixture("boxscore_nhl_401803067.json")
    boxscores = parse_team_boxscores("nhl", summary)
    assert len(boxscores) == 2

    by_team = {b.team: b for b in boxscores}
    assert set(by_team) == {"FLA", "BUF"}

    fla = by_team["FLA"]
    assert fla.game_id == "401803067"
    assert fla.league == "nhl"
    assert fla.is_home is False
    assert fla.opponent == "BUF"
    assert fla.stats["powerPlayGoals"] == 1.0
    assert fla.stats["powerPlayOpportunities"] == 1.0
    assert fla.stats["shotsTotal"] == 32.0

    buf = by_team["BUF"]
    assert buf.is_home is True
    assert buf.opponent == "FLA"
    assert buf.stats["powerPlayGoals"] == 0.0
    assert buf.stats["powerPlayOpportunities"] == 2.0
    assert buf.stats["shotsTotal"] == 23.0


def test_parse_nfl_boxscore_from_real_fixture():
    summary = _load_fixture("boxscore_nfl_401772977.json")
    boxscores = parse_team_boxscores("nfl", summary)
    assert len(boxscores) == 2

    by_team = {b.team: b for b in boxscores}
    assert set(by_team) == {"BUF", "JAX"}

    buf = by_team["BUF"]
    assert buf.game_id == "401772977"
    assert buf.league == "nfl"
    assert buf.is_home is False
    assert buf.opponent == "JAX"
    assert buf.stats["netPassingYards"] == 261.0
    assert buf.stats["rushingYards"] == 79.0
    assert buf.stats["totalYards"] == 340.0
    assert buf.stats["turnovers"] == 1.0
    assert buf.stats["totalOffensivePlays"] == 62.0

    jax = by_team["JAX"]
    assert jax.is_home is True
    assert jax.opponent == "BUF"
    assert jax.stats["totalYards"] == 359.0
    assert jax.stats["turnovers"] == 2.0


def test_parse_absent_boxscore_returns_empty_list():
    assert parse_team_boxscores("nba", {}) == []
    assert parse_team_boxscores("nba", {"boxscore": {}}) == []
    assert parse_team_boxscores("nba", {"header": {"id": "1"}, "boxscore": {"teams": []}}) == []
    assert parse_team_boxscores("nba", None) == []  # type: ignore[arg-type]


def test_parse_unsupported_league_returns_empty_list():
    summary = _load_fixture("boxscore_nba_401810960.json")
    assert parse_team_boxscores("mlb", summary) == []


def test_parse_single_team_boxscore_returns_empty_list():
    summary = _load_fixture("boxscore_nba_401810960.json")
    summary = dict(summary)
    summary["boxscore"] = {"teams": summary["boxscore"]["teams"][:1]}
    assert parse_team_boxscores("nba", summary) == []


def test_parse_missing_game_id_returns_empty_list():
    summary = _load_fixture("boxscore_nba_401810960.json")
    summary = dict(summary)
    summary["header"] = {}
    assert parse_team_boxscores("nba", summary) == []


# ---------------------------------------------------------------- store


def _boxscore(game_id: str, team: str = "PHI", opponent: str = "WSH") -> TeamBoxscore:
    return TeamBoxscore(
        game_id=game_id, league="nba", team=team, opponent=opponent,
        is_home=False, stats={"turnovers": 10.0},
    )


def test_store_ingest_returns_count_and_recent_is_newest_first(tmp_path):
    store = BoxscoreStore("nba", path=tmp_path / "boxscores_nba.json")
    added = store.ingest([_boxscore("g1"), _boxscore("g2")])
    assert added == 2
    recent = store.recent("PHI")
    assert [b.game_id for b in recent] == ["g2", "g1"]


def test_store_recent_unknown_team_is_empty(tmp_path):
    store = BoxscoreStore("nba", path=tmp_path / "boxscores_nba.json")
    assert store.recent("ZZZ") == []


def test_store_ingest_idempotent_by_game_id(tmp_path):
    store = BoxscoreStore("nba", path=tmp_path / "boxscores_nba.json")
    first = store.ingest([_boxscore("g1")])
    second = store.ingest([_boxscore("g1")])  # replay same game
    assert first == 1
    assert second == 0
    assert len(store.recent("PHI", n=50)) == 1


def test_store_ingest_mixed_new_and_duplicate(tmp_path):
    store = BoxscoreStore("nba", path=tmp_path / "boxscores_nba.json")
    store.ingest([_boxscore("g1")])
    added = store.ingest([_boxscore("g1"), _boxscore("g2")])
    assert added == 1  # only g2 is new
    assert len(store.recent("PHI", n=50)) == 2


def test_store_retention_cap_evicts_oldest(tmp_path):
    store = BoxscoreStore("nba", path=tmp_path / "boxscores_nba.json")
    for i in range(35):
        store.ingest([_boxscore(f"g{i}")])
    recent = store.recent("PHI", n=50)
    assert len(recent) == 30
    assert recent[0].game_id == "g34"  # newest first
    assert recent[-1].game_id == "g5"  # g0..g4 evicted (35 - 30 = 5)


def test_store_persists_and_reloads(tmp_path):
    path = tmp_path / "boxscores_nba.json"
    store = BoxscoreStore("nba", path=path)
    store.ingest([_boxscore("g1")])
    assert path.exists()

    reloaded = BoxscoreStore("nba", path=path)
    recent = reloaded.recent("PHI")
    assert len(recent) == 1
    assert recent[0].game_id == "g1"
    assert recent[0].stats == {"turnovers": 10.0}

    # Idempotency survives a reload.
    assert reloaded.ingest([_boxscore("g1")]) == 0


def test_store_missing_file_starts_empty(tmp_path):
    store = BoxscoreStore("nba", path=tmp_path / "does_not_exist.json")
    assert store.recent("PHI") == []


def test_store_corrupt_file_starts_empty_not_raise(tmp_path):
    path = tmp_path / "boxscores_nba.json"
    path.write_text("not json", encoding="utf-8")
    store = BoxscoreStore("nba", path=path)
    assert store.recent("PHI") == []


def test_store_default_path_uses_runtime_autonomy():
    store = BoxscoreStore("nhl")
    assert store.path == Path("runtime/autonomy/boxscores_nhl.json")
