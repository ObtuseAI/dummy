"""Phase 1: the sports historical data lake — point-in-time integrity.

The store must never let a prior see the future: a query as-of an instant t
returns only games that had already *finished* strictly before t. Everything
downstream (model cold-start priors, walk-forward backtests) leans on that.
"""
from __future__ import annotations

from autonomy.sports.history_store import SportsHistoryStore


def _game(gid, league, season, start, home, away, hs, as_, status, src="nflverse"):
    return {
        "game_id": gid, "league": league, "season": season, "start_time": start,
        "home": home, "away": away, "home_score": hs, "away_score": as_,
        "status": status, "source": src, "provenance_url": f"https://example/{gid}",
    }


def test_games_before_is_point_in_time(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    st.upsert_game(_game("nfl-1", "nfl", 2025, "2025-09-07T17:00:00Z", "KC", "BAL", 27, 20, "final"))
    st.upsert_game(_game("nfl-2", "nfl", 2025, "2025-09-14T17:00:00Z", "KC", "CIN", None, None, "scheduled"))

    # as-of after game 1 finished, before game 2: only the final game 1 is visible
    ids = [g["game_id"] for g in st.games_before("2025-09-10T00:00:00Z", league="nfl")]
    assert ids == ["nfl-1"]
    # as-of before game 1 started: nothing (no leakage of a not-yet-played game)
    assert st.games_before("2025-09-01T00:00:00Z") == []
    # a scheduled (not final) game is never returned even once its start passes
    assert st.games_before("2025-12-01T00:00:00Z", league="nfl") == [g for g in st.games_before("2025-12-01T00:00:00Z", league="nfl") if g["status"] == "final"]

    st.close()


def test_upsert_is_idempotent_and_updates(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    st.upsert_game(_game("g1", "nba", 2025, "2025-10-01T00:00:00Z", "BOS", "NYK", None, None, "scheduled"))
    st.upsert_game(_game("g1", "nba", 2025, "2025-10-01T00:00:00Z", "BOS", "NYK", 110, 104, "final"))
    rows = st.games(league="nba")
    assert len(rows) == 1 and rows[0]["home_score"] == 110 and rows[0]["status"] == "final"
    st.close()


def test_team_form_point_in_time(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    st.upsert_game(_game("g1", "nfl", 2025, "2025-09-07T17:00:00Z", "KC", "BAL", 27, 20, "final"))
    st.upsert_game(_game("g2", "nfl", 2025, "2025-09-14T17:00:00Z", "DEN", "KC", 17, 24, "final"))
    st.upsert_game(_game("g3", "nfl", 2025, "2025-09-21T17:00:00Z", "KC", "NYG", None, None, "scheduled"))
    form = st.team_form("KC", "2025-09-20T00:00:00Z", league="nfl")
    assert [g["game_id"] for g in form] == ["g2", "g1"]     # most-recent first, both final, both before t
    assert st.team_form("KC", "2025-09-08T00:00:00Z", league="nfl")[0]["game_id"] == "g1"
    st.close()


def test_ingest_checkpoint_roundtrip(tmp_path):
    st = SportsHistoryStore(tmp_path / "h.db")
    st.record_ingest("nflverse", "nfl", "2024", status="ok", rows=285, http={"calls": 1, "cache_hits": 0})
    st.record_ingest("nflverse", "nfl", "2025", status="ok", rows=90, http={"calls": 1, "cache_hits": 1})
    last = st.last_ingest("nflverse", "nfl")
    assert last["date_range"] == "2025" and last["rows"] == 90
    assert st.last_ingest("nflverse", "mlb") is None
    st.close()
