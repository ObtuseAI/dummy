"""Phase 1b: per-bet-type accuracy + improvement telemetry.

Every scope's graded quality is broken down by bet type (winner / total /
spread / prop / crypto contract family), each cell carries an improvement
trend (recent window vs prior window), and the payload rolls up an overall
accuracy + improvement plus a scope x bet-type matrix for the dashboard.
"""
from __future__ import annotations

import sqlite3

from autonomy.scope_analytics import (
    _improvement,
    append_accuracy_history,
    bet_type_of,
    build_scope_analytics,
    read_accuracy_series,
)


def test_bet_type_of_sports_and_crypto():
    assert bet_type_of("KXMLBGAME-26JUL19-NYYBOS") == "winner"
    assert bet_type_of("KXMLBTOTAL-26JUL19-NYYBOS") == "total"
    assert bet_type_of("KXMLBSPREAD-26JUL19-NYYBOS3") == "spread"
    assert bet_type_of("KXMLBHR-26JUL19-JUDGE") == "prop"
    assert bet_type_of("KXNBASPREAD-26JAN12DUKEUNC-DUKE4") == "spread"
    assert bet_type_of("KXBTCD-26JUL0917-T71249.99") == "ladder"
    assert bet_type_of("KXSOL15M-26JUL100415-15") == "15m_direction"
    assert bet_type_of("KXWHATEVER-1") == "other"


def test_improvement_detects_a_sharpening_trend():
    # prior half: predictions far from the result (high Brier);
    # recent half: predictions on the nose (low Brier) -> improving.
    recs = []
    for i in range(30):
        recs.append({"prob": 0.5, "result": 1, "market": None, "action": "ABSTAIN",
                     "settled_at": f"2026-01-{i + 1:03d}"})
    for i in range(30):
        recs.append({"prob": 0.95, "result": 1, "market": None, "action": "ABSTAIN",
                     "settled_at": f"2026-02-{i + 1:03d}"})
    imp = _improvement(recs)
    assert imp["trend"] == "improving"
    assert imp["delta_brier"] > 0            # Brier fell = sharper
    # and a flat series is flat
    flat = [{"prob": 0.6, "result": 1, "market": None, "action": "ABSTAIN",
             "settled_at": f"2026-03-{i + 1:03d}"} for i in range(60)]
    assert _improvement(flat)["trend"] == "flat"
    assert _improvement(recs[:4])["trend"] == "thin"


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE decisions(market_ticker TEXT, action TEXT, side TEXT,
            probability_yes REAL, market_implied_yes REAL,
            ev_cents REAL, price_cents INTEGER, created_at TEXT)"""
    )
    # Graded quality reads the fused forecast of record (phantom grading), so a
    # market we price counts even without a BUY decision. market_implied rides
    # in the fused features JSON.
    conn.execute(
        """CREATE TABLE signals(source TEXT, market_ticker TEXT,
            probability_yes REAL, created_at TEXT, features TEXT)"""
    )
    conn.execute("CREATE TABLE settlements(market_ticker TEXT, result_yes INTEGER, settled_at TEXT)")
    return conn


def _fused(conn, ticker, prob, days_ago, *, market=0.5):
    conn.execute(
        "INSERT INTO signals VALUES('fused_forecast', ?, ?, datetime('now', ?), ?)",
        (ticker, prob, f"-{days_ago + 1} days", f'{{"market_implied_yes": {market}}}'),
    )


def _settle(conn, ticker, prob, result, days_ago, *, traded=True):
    _fused(conn, ticker, prob, days_ago)
    if traded:
        conn.execute(
            "INSERT INTO decisions VALUES(?,?,?,?,?,?,?, datetime('now', ?))",
            (ticker, "BUY_YES", "YES", prob, 0.5, 3.0, 55, f"-{days_ago + 1} days"),
        )
    conn.execute(
        "INSERT INTO settlements VALUES(?,?, datetime('now', ?))",
        (ticker, result, f"-{days_ago} days"),
    )


def test_scope_payload_carries_bet_types_and_telemetry():
    conn = _conn()
    for i in range(6):
        _settle(conn, f"KXMLBGAME-26JUL{i:02d}-NYYBOS", 0.7, 1, 3 + i)   # MLB winner
        _settle(conn, f"KXMLBTOTAL-26JUL{i:02d}-NYYBOS", 0.6, 0, 3 + i)  # MLB total
    for i in range(6):
        _settle(conn, f"KXBTCD-26JUL{i:02d}17-T71249.99", 0.8, 1, 3 + i)  # BTC ladder
    conn.commit()

    out = build_scope_analytics(conn, season_active={"mlb": True})
    mlb = out["verticals"]["SPORTS"]["scopes"]["MLB"]
    assert set(mlb["bet_types"]) >= {"winner", "total"}
    assert mlb["bet_types"]["winner"]["summary"]["n"] == 6
    assert "improvement" in mlb and "trend" in mlb["improvement"]
    btc = out["verticals"]["CRYPTO"]["scopes"]["BTC"]
    assert "ladder" in btc["bet_types"]

    tel = out["telemetry"]
    assert tel["overall"]["summary"]["n"] == 18
    assert "improvement" in tel["overall"]
    # matrix has a row per (scope, bet_type) with data
    cells = {(c["scope"], c["bet_type"]) for c in tel["matrix"]}
    assert ("MLB", "winner") in cells and ("BTC", "ladder") in cells


def test_pick_board_and_settled_today():
    conn = _conn()
    # settled within the day: model right, then model wrong (winner bet type)
    for tick, prob, res, hrs in [("KXMLBGAME-A-NYYBOS", 0.72, 1, 5), ("KXMLBGAME-B-LADSF", 0.68, 0, 8)]:
        conn.execute("INSERT INTO signals VALUES('fused_forecast', ?, ?, datetime('now','-1 days'), ?)",
                     (tick, prob, '{"market_implied_yes": 0.5}'))
        conn.execute("INSERT INTO decisions VALUES(?,?,?,?,?,?,?, datetime('now','-1 days'))",
                     (tick, "BUY_YES", "YES", prob, 0.5, 3.0, 55))
        conn.execute("INSERT INTO settlements VALUES(?,?, datetime('now', ?))", (tick, res, f"-{hrs} hours"))
    # an OPEN pick (unsettled) on a total -> shows in the pick board
    conn.execute("INSERT INTO decisions VALUES('KXMLBTOTAL-C-NYYBOS','BUY_YES','YES',0.61,0.53,4.2,49, datetime('now'))")
    conn.commit()

    mlb = build_scope_analytics(conn, season_active={"mlb": True})["verticals"]["SPORTS"]["scopes"]["MLB"]
    # req 4: settled-today with correct/incorrect
    st = {r["ticker"]: r for r in mlb["settled_today"]}
    assert st["KXMLBGAME-A-NYYBOS"]["correct"] is True
    assert st["KXMLBGAME-B-LADSF"]["correct"] is False
    assert all(r["bet_type"] == "winner" for r in mlb["settled_today"])
    # req 3: open picks grouped by bet type
    assert "total" in mlb["pick_board"]
    assert mlb["pick_board"]["total"][0]["ticker"] == "KXMLBTOTAL-C-NYYBOS"


def test_accuracy_history_appends_and_bounds(tmp_path):
    p = tmp_path / "acc.jsonl"
    a = append_accuracy_history({"overall": {"summary": {"n": 100, "brier": 0.20, "hit_rate": 0.70, "brier_edge": 0.01}}}, "2026-07-19T00:00:00", path=p)
    b = append_accuracy_history({"overall": {"summary": {"n": 110, "brier": 0.19, "hit_rate": 0.72, "brier_edge": 0.02}}}, "2026-07-19T00:20:00", path=p)
    assert a and b
    series = read_accuracy_series(path=p)
    assert [s["brier"] for s in series] == [0.20, 0.19]     # oldest -> newest
    # nothing graded -> skipped, never an empty row
    assert append_accuracy_history({"overall": {"summary": {"n": 0}}}, "t", path=p) is None
    assert len(read_accuracy_series(path=p)) == 2
    # missing file reads empty, never raises
    assert read_accuracy_series(path=tmp_path / "nope.jsonl") == []
