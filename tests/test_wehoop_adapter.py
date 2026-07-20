"""Phase 1: wehoop WNBA schedule -> lake (no network; fixture CSV)."""
from __future__ import annotations

from autonomy.ingest.fetcher import PoliteFetcher
from autonomy.ingest.wehoop import ingest_wehoop_wnba, parse_wehoop_schedule
from autonomy.sports.history_store import SportsHistoryStore

CSV = (
    "id,date,status_type_completed,home_abbreviation,home_score,home_winner,away_abbreviation,away_score,away_winner\n"
    "401620001,2023-05-19T23:00Z,true,LV,89,true,SEA,74,false\n"
    "401620999,2023-09-01T23:00Z,false,NY,,false,CONN,,false\n"
)


class FakeTransport:
    def __init__(self, script):
        self.script = list(script)

    def __call__(self, url, params, headers):
        return self.script.pop(0)


def test_parse_and_ingest_dedup(tmp_path):
    games = parse_wehoop_schedule(CSV, 2023)
    assert len(games) == 2 and games[0]["home"] == "LV" and games[0]["home_score"] == 89
    assert games[1]["status"] == "scheduled"

    store = SportsHistoryStore(tmp_path / "h.db")
    f = PoliteFetcher(cache_dir=tmp_path / "c", transport=FakeTransport([(200, CSV, {})]),
                      clock=lambda: 0.0, sleep=lambda s: None, min_interval=0.0)
    res = ingest_wehoop_wnba(store, f, [2023])
    assert res["seasons"] == 1
    finals = store.games_before("2024-01-01T00:00:00Z", league="wnba")
    assert [g["game_id"] for g in finals] == ["401620001"]
    store.close()
