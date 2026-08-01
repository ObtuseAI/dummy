"""Phase 1: ESPN scoreboard -> history lake, all leagues (no network)."""
from __future__ import annotations

from autonomy.ingest.espn_lake import espn_games_to_rows, ingest_espn_league
from autonomy.sports.espn import Game
from autonomy.sports.history_store import SportsHistoryStore


class FakeEspn:
    def __init__(self, by_league):
        self.by_league = by_league
        self.calls = []

    def games(self, league, dates=None):
        self.calls.append((league, dates))
        return self.by_league.get(league, [])

    def games_or_raise(self, league, dates=None):
        self.calls.append((league, dates))
        return self.by_league.get(league, [])


class DeadFeedEspn:
    """A client whose upstream fetch is broken.

    ``games`` honours its documented swallow-to-empty contract; only
    ``games_or_raise`` surfaces the failure. A lake ingest that calls the
    former cannot tell a dead feed from an empty slate.
    """

    def __init__(self):
        self.games_calls = 0
        self.raising_calls = 0

    def games(self, league, dates=None):
        self.games_calls += 1
        return []

    def games_or_raise(self, league, dates=None):
        self.raising_calls += 1
        raise RuntimeError("upstream 503")


def test_a_dead_feed_is_recorded_as_an_error_not_an_empty_slate(tmp_path):
    """A broken feed must not be logged as a successful zero-row ingest.

    Regression for a silent seven-day outage: the lake took no rows from
    2026-07-24 onward while every scheduled ingest recorded status "ok"
    with rows 0, because the swallowing ``games`` turned every transport
    failure into an empty slate. An in-season league with a dead feed and
    an in-season league with no fixtures produced byte-identical log rows,
    so no monitor could tell them apart.
    """
    store = SportsHistoryStore(tmp_path / "h.db")
    client = DeadFeedEspn()

    result = ingest_espn_league(store, client, "mlb")

    assert result["ok"] is False
    assert result["rows"] == 0
    assert client.raising_calls == 1, "the ingest must use the raising variant"
    assert client.games_calls == 0, "the swallowing variant hides transport failure"

    logged = store.conn.execute(
        "SELECT status, rows FROM ingest_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert logged[0] == "error:RuntimeError"
    assert logged[1] == 0
    store.close()


def _g(gid, league, home, away, status, hs=None, as_=None, date="2025-11-01T00:00Z", won=None,
       home_ml=None, away_ml=None, home_ml_open=None, away_ml_open=None):
    return Game(game_id=gid, league=league, home=home, away=away, status=status,
                home_won=won, date=date, home_score=hs, away_score=as_,
                home_ml=home_ml, away_ml=away_ml, home_ml_open=home_ml_open,
                away_ml_open=away_ml_open, odds_provider="ESPN BET")


def test_moneylines_become_closing_line_history(tmp_path):
    from autonomy.ingest.espn_lake import espn_games_to_lines
    from autonomy.sports.history_store import SportsHistoryStore

    game = _g("m1", "nba", "BOS", "NYK", "post", 110, 104, won=True,
              home_ml=-150, away_ml=130, home_ml_open=-135, away_ml_open=115)
    lines = espn_games_to_lines([game])
    # home+away, open+close => 4 rows
    assert len(lines) == 4
    st = SportsHistoryStore(tmp_path / "h.db")
    st.record_lines(lines)
    got = {ln["ticker"]: ln for ln in st.lines_for("m1")}
    assert got["espnml:m1:home:close"]["price"] == -150 and got["espnml:m1:home:close"]["is_close"] == 1
    assert got["espnml:m1:home:open"]["price"] == -135 and got["espnml:m1:home:open"]["is_close"] == 0
    st.close()


def test_status_and_season_mapping():
    rows = espn_games_to_rows([
        _g("1", "nba", "BOS", "NYK", "post", 110, 104, won=True),
        _g("2", "nba", "LAL", "GSW", "pre"),
    ])
    by = {r["game_id"]: r for r in rows}
    assert by["1"]["status"] == "post" and by["1"]["season"] == 2025 and by["1"]["home_score"] == 110
    assert by["2"]["status"] == "scheduled" and by["2"]["home_score"] is None
    assert by["1"]["result_available_at"] is None
    assert by["1"]["provenance_quality"] == "unknown"


def test_ingest_all_leagues_point_in_time(tmp_path):
    store = SportsHistoryStore(tmp_path / "h.db")
    client = FakeEspn({
        "nba": [_g("n1", "nba", "BOS", "NYK", "post", 110, 104, date="2025-11-01T00:00Z", won=True),
                _g("n2", "nba", "LAL", "GSW", "pre", date="2025-11-05T00:00Z")],
        "wnba": [_g("w1", "wnba", "LV", "NY", "post", 90, 85, date="2025-08-01T00:00Z", won=True)],
    })
    for league in ("nba", "wnba"):
        res = ingest_espn_league(
            store, client, league, received_at="2025-11-02T00:00:00+00:00")
        assert res["ok"]
    # all leagues represented; only finished games are point-in-time visible
    assert {g["game_id"] for g in store.games_before("2025-12-01T00:00:00Z")} == {"n1", "w1"}
    assert store.games(league="wnba")[0]["home"] == "LV"
    strict = store.evaluation_games()
    assert {game["game_id"] for game in strict} == {"n1", "w1"}
    by = {game["game_id"]: game for game in strict}
    # n1 was observed the day after it started: a genuine live observation.
    assert by["n1"]["provenance_quality"] == "observed_at_receipt"
    assert by["n1"]["result_available_at"] == by["n1"]["received_at"]
    # w1 was observed ~3 months after it started: a retro backfill must not
    # claim today's receipt as first availability — it carries the derived
    # source-reported bound (start + 12h) and stays evaluation-eligible.
    assert by["w1"]["provenance_quality"] == "source_reported"
    assert by["w1"]["result_available_at"] == "2025-08-01T12:00:00+00:00"
    assert by["w1"]["received_at"] == "2025-11-02T00:00:00+00:00"
    store.close()


def test_down_feed_is_fail_soft(tmp_path):
    store = SportsHistoryStore(tmp_path / "h.db")

    class Boom:
        def games(self, league, dates=None):
            raise RuntimeError("feed down")

    res = ingest_espn_league(store, Boom(), "nhl")
    assert res["ok"] is False and store.games() == []
    assert store.last_ingest("espn", "nhl")["status"].startswith("error")
    store.close()
