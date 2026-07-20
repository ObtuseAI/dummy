"""Phase 1: cfbfastR NCAAF games index -> lake (no network; fixture CSV)."""
from __future__ import annotations

from autonomy.ingest.cfbfastr import ingest_cfbd_games, parse_cfbd_games
from autonomy.ingest.fetcher import PoliteFetcher
from autonomy.sports.history_store import SportsHistoryStore

CSV = (
    "game_id,season,week,start_date,home_team,home_points,away_team,away_points,home_conference,away_conference,PBP\n"
    "401238035,2020,1,2020-09-04T00:00:00.000Z,UAB,45,Central Arkansas,35,Conference USA,NA,TRUE\n"
    "401300000,2021,2,2021-09-11T00:00:00.000Z,Texas,58,Rice,0,Big 12,American,TRUE\n"
    "401400000,2026,1,2026-09-05T00:00:00.000Z,Alabama,NA,Georgia,NA,SEC,SEC,FALSE\n"   # unplayed
)


class FakeTransport:
    def __init__(self, script):
        self.script = list(script)

    def __call__(self, url, params, headers):
        return self.script.pop(0)


def test_parse_maps_ncaaf_results():
    games = parse_cfbd_games(CSV)
    assert len(games) == 3
    by = {g["game_id"]: g for g in games}
    assert by["cfb-401238035"]["league"] == "ncaaf" and by["cfb-401238035"]["home"] == "UAB"
    assert by["cfb-401238035"]["home_score"] == 45 and by["cfb-401238035"]["status"] == "final"
    assert by["cfb-401400000"]["status"] == "scheduled" and by["cfb-401400000"]["home_score"] is None


def test_ingest_point_in_time(tmp_path):
    store = SportsHistoryStore(tmp_path / "h.db")
    f = PoliteFetcher(cache_dir=tmp_path / "c", transport=FakeTransport([(200, CSV, {})]),
                      clock=lambda: 0.0, sleep=lambda s: None, min_interval=0.0)
    res = ingest_cfbd_games(store, f)
    assert res["ok"] and res["rows"] == 3
    finals = store.games_before("2026-01-01T00:00:00Z", league="ncaaf")
    assert {g["game_id"] for g in finals} == {"cfb-401238035", "cfb-401300000"}
    store.close()
