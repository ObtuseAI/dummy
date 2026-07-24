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
            decision_id TEXT DEFAULT '', market_ticker TEXT, action TEXT, side TEXT,
            probability_yes REAL, market_implied_yes REAL,
            ev_cents REAL, price_cents INTEGER, created_at TEXT)"""
    )
    # Full signals schema, not a 5-column stand-in: grading reads the
    # ``signal_history`` UNION view, which selects every archived column and
    # orders by ``id``. A fixture missing those columns silently diverges from
    # the real ledger and hides exactly the archive-truncation class of bug.
    conn.execute(
        """CREATE TABLE signals(
            id INTEGER PRIMARY KEY, source TEXT, market_ticker TEXT,
            probability_yes REAL, uncertainty REAL, rationale TEXT,
            created_at TEXT, mode TEXT, features TEXT,
            ingested_at TEXT, ingest_version TEXT)"""
    )
    conn.execute(
        "CREATE TABLE settlements(market_ticker TEXT, result_yes INTEGER, settled_at TEXT)"
    )
    return conn


def _add_settled(conn, ticker, *, prob, result, days_ago, traded=True):
    # Grading reads the fused forecast of record -> a league we price shows up
    # even with no BUY decision (phantom grading).
    conn.execute(
        "INSERT INTO signals(source,market_ticker,probability_yes,created_at,mode,features)"
        " VALUES('fused_forecast', ?, ?, datetime('now', ?), 'live', ?)",
        (ticker, prob, f"-{days_ago + 1} days", '{"market_implied_yes": 0.5}'),
    )
    if traded:
        conn.execute(
            "INSERT INTO decisions(market_ticker,action,side,probability_yes,market_implied_yes,ev_cents,price_cents,created_at) VALUES(?,?,?,?,?,?,?, datetime('now', ?))",
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
    assert sports["MLB"]["season_status"] == "in"          # active + grading now

    # WNBA has no current-window grade, so it falls back to last season and reads
    # "upcoming" (active, but not yet playing this window) -- never "in season".
    assert sports["WNBA"]["in_season"] is True
    assert sports["WNBA"]["basis"] == "last-season"
    assert sports["WNBA"]["summary"]["n"] == 1
    assert sports["WNBA"]["season_status"] == "upcoming"

    # NBA is out of season with no history at all -> listed, flagged, empty.
    assert sports["NBA"]["in_season"] is False
    assert sports["NBA"]["basis"] == "none"
    assert sports["NBA"]["summary"]["n"] == 0
    assert sports["NBA"]["season_status"] == "off"

    # Every roster league is wired to ITS OWN scope -- no basketball/football
    # league is folded into another (WNBA != NBA, NFL != NCAAF, ...).
    for lg in SPORTS_ROSTER:
        assert sports[lg]["label"] == lg


def test_every_league_wired_to_its_own_scope_no_coupling():
    """Each league's Kalshi series classifies to ITS OWN league -- WNBA is never
    folded into NBA/NCAAMB, NFL never into NCAAF. Guards against the sibling
    coupling that silently drops or merges a league's markets."""
    from autonomy.picks import _scope_of
    from autonomy.scope_analytics import bet_type_of, scope_key
    from autonomy.sports_markets import is_known_sports_market

    canonical = {
        "MLB": "KXMLBGAME-26JUL19NYYBOS-NYY",
        "WNBA": "KXWNBAGAME-26JUL19NYLLV-NYL",
        "NBA": "KXNBAGAME-26NOV02LALBOS-LAL",
        "NFL": "KXNFLGAME-26SEP07KCBAL-KC",
        "NHL": "KXNHLGAME-26OCT08BOSFLA-BOS",
        "NCAAF": "KXNCAAFGAME-26AUG30ALAGA-ALA",
        "NCAAMB": "KXNCAAMBGAME-26NOV04DUKEKU-DUKE",
    }
    for lg in SPORTS_ROSTER:
        tk = canonical[lg]
        assert is_known_sports_market(tk), f"{lg} series not in the registry"
        assert _scope_of(tk)[0] == lg.lower(), f"{lg} misclassified by _scope_of"
        assert scope_key(tk) == ("SPORTS", lg), f"{lg} misrouted by scope_key"
        assert bet_type_of(tk) == "winner"
    # Explicit sibling non-coupling.
    assert scope_key(canonical["WNBA"]) != scope_key(canonical["NBA"])
    assert scope_key(canonical["NFL"]) != scope_key(canonical["NCAAF"])


def test_forecast_without_a_trade_still_grades_the_scope():
    """A league we PRICE but never take a BUY side on (0 decisions) still shows
    graded quality -- the WNBA-missing-everything bug: grading joined settlements
    to decisions, so phantom-graded scopes vanished."""
    conn = _mk_conn()
    for i in range(6):
        _add_settled(conn, f"KXWNBAGAME-26JUL{i:02d}NYLLV-NYL", prob=0.7, result=1,
                     days_ago=2 + i, traded=False)   # forecast + settled, never traded
    conn.commit()
    wnba = build_scope_analytics(conn, season_active={"wnba": True})["verticals"]["SPORTS"]["scopes"]["WNBA"]
    assert wnba["summary"]["n"] == 6            # graded despite zero decisions
    assert wnba["summary"]["traded"] == 0       # honestly marked untraded
    assert wnba["basis"] == "current"
    assert wnba["season_status"] == "in"
    assert "winner" in wnba["bet_types"]


def test_unknown_season_defaults_in_season():
    # A league the SeasonMonitor has never verdicted defaults to in-season
    # (matches the monitor's fail-open default) rather than reading as dormant.
    conn = _mk_conn()
    conn.commit()
    out = build_scope_analytics(conn, season_active={})
    sports = out["verticals"]["SPORTS"]["scopes"]
    assert set(SPORTS_ROSTER) <= set(sports)
    assert all(sports[lg]["in_season"] is True for lg in SPORTS_ROSTER)


def test_open_nfl_pick_without_current_grade_is_upcoming_not_in_season():
    conn = _mk_conn()
    conn.execute(
        "INSERT INTO decisions(market_ticker,action,side,probability_yes,market_implied_yes,ev_cents,price_cents,created_at) VALUES(?,?,?,?,?,?,?, datetime('now'))",
        (
            "KXNFLGAME-26SEP07KCBAL-KC",
            "BUY_YES",
            "YES",
            0.61,
            0.55,
            4.0,
            55,
        ),
    )
    conn.commit()

    nfl = build_scope_analytics(
        conn,
        season_active={"nfl": True},
    )["verticals"]["SPORTS"]["scopes"]["NFL"]

    assert len(nfl["picks"]) == 1
    assert nfl["summary"]["n"] == 0
    assert nfl["basis"] == "none"
    assert nfl["season_status"] == "upcoming"
