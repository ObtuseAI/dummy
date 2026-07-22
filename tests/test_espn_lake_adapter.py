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
    assert all(game["provenance_quality"] == "observed_at_receipt" for game in strict)
    assert all(game["result_available_at"] == game["received_at"] for game in strict)
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
