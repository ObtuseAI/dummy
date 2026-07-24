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


# Wave-85 added NHL. It had been excluded as "NHL-API-keyed rather than
# ESPN-schema", but the field fallbacks already cover exactly that shape -- the
# NAME_CSV case below is described as fastRhockey-style and has always passed.
# Verified against the real feed: 16,578 completed games across 2011-2024, and
# NHL went from 0 games in the lake (not_repriceable) to a graded walk-forward.
def test_all_leagues_mapped():
    assert set(SDV_SOURCES) == {"wnba", "nba", "ncaamb", "nhl"}


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


def test_schedule_prefers_timezone_aware_date_key():
    """A naive date silently quarantines every row it parses.

    stamp_retro_source_reported() derives result availability through
    _parse_aware, which REJECTS a timezone-naive value, so rows keyed off a
    bare "game_date" stay provenance_quality=unknown and the point-in-time
    walk-forward excludes them outright. That is how 16,578 successfully
    ingested NHL games still graded as "no completed games in the lake yet":
    fastRhockey publishes both game_date ("2023-06-14") and game_date_time
    ("2023-06-14T00:00:00Z"), and only the latter can be stamped.
    """
    from autonomy.ingest.provenance import stamp_retro_source_reported
    from autonomy.ingest.sportsdataverse import parse_sdv_schedule

    text = (
        "game_id,home_team_name,away_team_name,game_date,game_date_time,"
        "home_score,away_score,status_detailed_state\n"
        "401,Bruins,Canucks,2023-06-14,2023-06-14T00:00:00Z,4,0,Final\n"
    )
    rows = parse_sdv_schedule(text, "nhl", 2023, url="u")
    assert len(rows) == 1
    assert rows[0]["start_time"] == "2023-06-14T00:00:00Z"   # aware key wins
    assert rows[0]["status"] == "final"

    # The whole point: it must actually stamp, or the row is invisible.
    assert stamp_retro_source_reported(rows) == 1
    assert rows[0]["provenance_quality"] == "source_reported"


def test_schedule_still_accepts_date_only_repos():
    """Tolerance is preserved: a repo with only a bare date still parses."""
    from autonomy.ingest.sportsdataverse import parse_sdv_schedule

    text = (
        "game_id,home_team_name,away_team_name,game_date,"
        "home_score,away_score,status_detailed_state\n"
        "402,Bruins,Canucks,2023-06-14,4,0,Final\n"
    )
    rows = parse_sdv_schedule(text, "nhl", 2023, url="u")
    assert len(rows) == 1
    assert rows[0]["start_time"] == "2023-06-14"


def test_nhl_is_a_registered_history_source():
    """NHL was the one league with zero games in the lake."""
    from autonomy.ingest.sportsdataverse import SDV_SOURCES

    assert SDV_SOURCES["nhl"] == ("fastRhockey-data", "nhl", "nhl")
