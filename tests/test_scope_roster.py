"""Wave-55: the SPORTS board lists the full league roster, always.

Every covered league appears as a scope even with no in-window grades:
in-season leagues show their current figures; out-of-season leagues carry an
``in_season=False`` flag and fall back to last-season grades (a widened
lookback) instead of vanishing from the board.
"""
from __future__ import annotations

import sqlite3

from autonomy.scope_analytics import SPORTS_ROSTER, build_scope_analytics


def _mk_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE decisions(
            market_ticker TEXT, action TEXT, side TEXT,
            probability_yes REAL, market_implied_yes REAL,
            ev_cents REAL, price_cents INTEGER, created_at TEXT)"""
    )
    conn.execute(
        "CREATE TABLE settlements(market_ticker TEXT, result_yes INTEGER, settled_at TEXT)"
    )
    return conn


def _add_settled(conn, ticker, *, prob, result, days_ago):
    conn.execute(
        "INSERT INTO decisions VALUES(?,?,?,?,?,?,?, datetime('now', ?))",
        (ticker, "BUY_YES", "YES", prob, 0.5, 3.0, 55, f"-{days_ago + 1} days"),
    )
    conn.execute(
        "INSERT INTO settlements VALUES(?,?, datetime('now', ?))",
        (ticker, result, f"-{days_ago} days"),
    )


def test_full_roster_listed_with_season_and_last_season_fallback():
    conn = _mk_conn()
    # MLB: settled inside the current window (in season).
    _add_settled(conn, "KXMLBGAME-26JUL19-NYYBOS", prob=0.7, result=1, days_ago=3)
    # WNBA: settled only OUTSIDE the 120d window but inside the last-season
    # lookback (in season now, but its grades are from last season's slate).
    _add_settled(conn, "KXWNBAGAME-26JAN10-LASLV", prob=0.6, result=1, days_ago=210)
    conn.commit()

    season_active = {
        "mlb": True, "wnba": True,
        "nba": False, "nfl": False, "nhl": False, "ncaaf": False, "ncaamb": False,
    }
    out = build_scope_analytics(conn, season_active=season_active)
    sports = out["verticals"]["SPORTS"]["scopes"]

    # Every roster league is present, none dropped for lack of in-window data.
    for lg in SPORTS_ROSTER:
        assert lg in sports, f"{lg} missing from the board"

    assert sports["MLB"]["in_season"] is True
    assert sports["MLB"]["basis"] == "current"
    assert sports["MLB"]["summary"]["n"] == 1

    # WNBA has no current-window grade, so it falls back to last season.
    assert sports["WNBA"]["in_season"] is True
    assert sports["WNBA"]["basis"] == "last-season"
    assert sports["WNBA"]["summary"]["n"] == 1

    # NBA is out of season with no history at all -> listed, flagged, empty.
    assert sports["NBA"]["in_season"] is False
    assert sports["NBA"]["basis"] == "none"
    assert sports["NBA"]["summary"]["n"] == 0


def test_unknown_season_defaults_in_season():
    # A league the SeasonMonitor has never verdicted defaults to in-season
    # (matches the monitor's fail-open default) rather than reading as dormant.
    conn = _mk_conn()
    conn.commit()
    out = build_scope_analytics(conn, season_active={})
    sports = out["verticals"]["SPORTS"]["scopes"]
    assert set(SPORTS_ROSTER) <= set(sports)
    assert all(sports[lg]["in_season"] is True for lg in SPORTS_ROSTER)
