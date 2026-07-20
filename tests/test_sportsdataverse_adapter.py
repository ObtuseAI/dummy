"""Phase 1: generic sportsdataverse schedule adapter (no network)."""
from __future__ import annotations

from autonomy.ingest.fetcher import PoliteFetcher
from autonomy.ingest.sportsdataverse import SDV_SOURCES, ingest_sdv_schedule, parse_sdv_schedule
from autonomy.sports.history_store import SportsHistoryStore

CSV = (
    "id,date,status_type_completed,home_abbreviation,home_score,away_abbreviation,away_score\n"
    "401590001,2023-10-24T23:00Z,true,BOS,108,NYK,104\n"
    "401590999,2024-04-01T23:00Z,false,LAL,,GSW,\n"
)


class FakeTransport:
    def __init__(self, script):
        self.script = list(script)

    def __call__(self, url, params, headers):
        return self.script.pop(0)


# ESPN-schema repos only (NHL's fastRhockey feed is NHL-API-keyed -> excluded).
def test_all_leagues_mapped():
    assert set(SDV_SOURCES) == {"wnba", "nba", "ncaamb"}


# A name-keyed schema (fastRhockey-style) still parses via the field fallbacks.
NAME_CSV = (
    "game_id,game_date,home_team_name,home_score,away_team_name,away_score,status_detailed_state\n"
    "77,2023-10-10,Boston Bruins,4,Chicago Blackhawks,1,Final\n"
)


def test_parse_and_ingest(tmp_path):
    games = parse_sdv_schedule(CSV, "nba", 2024)
    assert games[0]["home"] == "BOS" and games[0]["home_score"] == 108 and games[0]["status"] == "final"
    assert games[1]["status"] == "scheduled"

    named = parse_sdv_schedule(NAME_CSV, "nhl", 2023)
    assert named[0]["home"] == "Boston Bruins" and named[0]["status"] == "final" and named[0]["game_id"] == "77"
    store = SportsHistoryStore(tmp_path / "h.db")
    f = PoliteFetcher(cache_dir=tmp_path / "c", transport=FakeTransport([(200, CSV, {})]),
                      clock=lambda: 0.0, sleep=lambda s: None, min_interval=0.0)
    res = ingest_sdv_schedule(store, f, "nba", [2024])
    assert res["ok"] and res["seasons"] == 1
    assert [g["game_id"] for g in store.games_before("2024-06-01T00:00:00Z", league="nba")] == ["401590001"]
    store.close()
