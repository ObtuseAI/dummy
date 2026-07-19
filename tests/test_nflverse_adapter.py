"""Phase 1: nflverse games adapter -> history lake (no network; fixture CSV)."""
from __future__ import annotations

from autonomy.ingest.fetcher import PoliteFetcher
from autonomy.ingest.nflverse import ingest_nflverse_games, parse_nflverse_games
from autonomy.sports.history_store import SportsHistoryStore

CSV = (
    "game_id,season,game_type,week,gameday,gametime,away_team,away_score,home_team,home_score\n"
    "2024_01_BAL_KC,2024,REG,1,2024-09-05,20:20,BAL,20,KC,27\n"
    "2024_02_KC_DEN,2024,REG,2,2024-09-12,20:20,KC,24,DEN,17\n"
    "2025_01_DAL_PHI,2025,REG,1,2025-09-04,20:20,DAL,,PHI,\n"      # not yet played
)


class FakeTransport:
    def __init__(self, script):
        self.script = list(script)

    def __call__(self, url, params, headers):
        return self.script.pop(0)


def _fetcher(tmp_path):
    return PoliteFetcher(cache_dir=tmp_path / "cache", transport=FakeTransport([(200, CSV, {})]),
                         clock=lambda: 0.0, sleep=lambda s: None, min_interval=0.0)


def test_parse_maps_scores_and_status():
    games = parse_nflverse_games(CSV)
    assert len(games) == 3
    played = {g["game_id"]: g for g in games if g["status"] == "final"}
    assert set(played) == {"2024_01_BAL_KC", "2024_02_KC_DEN"}
    assert played["2024_01_BAL_KC"]["home"] == "KC" and played["2024_01_BAL_KC"]["home_score"] == 27
    scheduled = [g for g in games if g["status"] == "scheduled"]
    assert scheduled[0]["home_score"] is None


def test_ingest_lands_in_store_point_in_time(tmp_path):
    store = SportsHistoryStore(tmp_path / "h.db")
    res = ingest_nflverse_games(store, _fetcher(tmp_path))
    assert res["ok"] and res["rows"] == 3
    # as-of mid-2025: only the two finished 2024 games are visible
    before = store.games_before("2025-01-01T00:00:00Z", league="nfl")
    assert [g["game_id"] for g in before] == ["2024_02_KC_DEN", "2024_01_BAL_KC"]
    # the unplayed 2025 game never leaks even after its date
    later = store.games_before("2025-12-01T00:00:00Z", league="nfl")
    assert all(g["status"] == "final" for g in later)
    assert store.last_ingest("nflverse", "nfl")["rows"] == 3
    store.close()


def test_ingest_is_idempotent(tmp_path):
    store = SportsHistoryStore(tmp_path / "h.db")
    f = _fetcher(tmp_path)
    ingest_nflverse_games(store, f)
    # second run hits the cache (transport script is exhausted; a real call would IndexError)
    res2 = ingest_nflverse_games(store, f)
    assert res2["ok"] and res2["from_cache"] is True
    assert len(store.games(league="nfl")) == 3      # no duplicates
    store.close()
