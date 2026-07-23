"""Wave-74 football-organization reports: self-scout, film room, recruiting board."""
from __future__ import annotations

import json
import sqlite3

from autonomy.film_room import build_film_room
from autonomy.recruiting_board import build_recruiting_board
from autonomy.self_scout import build_self_scout


def _db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE signals(
            id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, market_ticker TEXT,
            probability_yes REAL, uncertainty REAL, rationale TEXT, created_at TEXT,
            mode TEXT, features TEXT, ingested_at TEXT, ingest_version INTEGER
        );
        CREATE TABLE settlements(market_ticker TEXT PRIMARY KEY, result_yes INTEGER);
        """
    )
    return conn


def _add(conn, source, ticker, prob, result, created="2026-07-20T12:00:00+00:00",
         features="{}"):
    conn.execute(
        "INSERT INTO signals(source, market_ticker, probability_yes, uncertainty,"
        " rationale, created_at, mode, features, ingested_at, ingest_version)"
        " VALUES (?,?,?,0.1,'',?,'live',?, '',2)",
        (source, ticker, prob, created, features),
    )
    conn.execute(
        "INSERT OR IGNORE INTO settlements VALUES (?,?)", (ticker, result),
    )


# ---------------------------------------------------------------- self-scout

def test_self_scout_flags_yes_lean_and_overconfidence():
    conn = _db()
    # 80 forecasts at 0.75 YES but only ~half resolve YES: leaned + overconfident.
    for i in range(80):
        _add(conn, "fused_forecast", f"T-{i:03d}", 0.75, 1 if i % 2 == 0 else 0)
    report = build_self_scout(conn, days=None)
    assert report["status"] == "OK"
    assert "directional_lean_yes" in report["warnings"]
    assert "overconfident_forecasts" in report["warnings"]
    assert report["self_scout_clean"] is False
    assert report["band_calibration"]["favorite"]["gap"] > 0.2


def test_self_scout_clean_when_calibrated():
    conn = _db()
    # Forecasts match outcomes: 70% bucket resolves 70% YES.
    for i in range(100):
        _add(conn, "fused_forecast", f"C-{i:03d}", 0.70, 1 if i % 10 < 7 else 0)
    report = build_self_scout(conn, days=None)
    assert report["status"] == "OK"
    assert "directional_lean_yes" not in report["warnings"]


def test_self_scout_insufficient_rows():
    conn = _db()
    _add(conn, "fused_forecast", "X-1", 0.6, 1)
    assert build_self_scout(conn, days=None)["status"] == "INSUFFICIENT_ROWS"


# ---------------------------------------------------------------- film room

def test_film_room_surfaces_worst_misses_with_dissenters():
    conn = _db()
    now = "datetime('now')"
    # A confident miss: fused 0.9 -> settled NO. Elo dissented at 0.45.
    conn.execute(
        "INSERT INTO signals(source, market_ticker, probability_yes, uncertainty,"
        " rationale, created_at, mode, features, ingested_at, ingest_version)"
        f" VALUES ('fused_forecast','MISS-1',0.9,0.1,'',{now},'live','{{\"tier\": \"B\"}}','',2)"
    )
    conn.execute(
        "INSERT INTO signals(source, market_ticker, probability_yes, uncertainty,"
        " rationale, created_at, mode, features, ingested_at, ingest_version)"
        f" VALUES ('sports_elo','MISS-1',0.45,0.1,'',{now},'live','{{}}','',2)"
    )
    conn.execute(
        "INSERT INTO signals(source, market_ticker, probability_yes, uncertainty,"
        " rationale, created_at, mode, features, ingested_at, ingest_version)"
        f" VALUES ('market_prior','MISS-1',0.55,0.1,'',{now},'live','{{}}','',2)"
    )
    conn.execute("INSERT INTO settlements VALUES ('MISS-1', 0)")
    # A good call for contrast.
    conn.execute(
        "INSERT INTO signals(source, market_ticker, probability_yes, uncertainty,"
        " rationale, created_at, mode, features, ingested_at, ingest_version)"
        f" VALUES ('fused_forecast','GOOD-1',0.8,0.1,'',{now},'live','{{}}','',2)"
    )
    conn.execute("INSERT INTO settlements VALUES ('GOOD-1', 1)")

    report = build_film_room(conn, days=30.0, reel_size=5)
    assert report["reel"], "expected at least one play"
    worst = report["reel"][0]
    assert worst["ticker"] == "MISS-1"
    assert worst["worse_than_market"] is True
    assert "sports_elo" in worst["sources_that_saw_it_better"]
    assert worst["tier"] == "B"


# ---------------------------------------------------------- recruiting board

def test_recruiting_board_merges_pipelines_and_needs(tmp_path):
    runtime = tmp_path
    (runtime / "mined_rule_forward_registry.json").write_text(json.dumps({
        "rules": {
            "aa": {"rule": "setup_score > 0.5", "status": "FORWARD_POSITIVE",
                   "forward": {"n_clusters": 45, "mean_edge": 0.01}},
            "bb": {"rule": "rsi <= 30", "status": "FORWARD_NEGATIVE",
                   "forward": {"n_clusters": 30, "mean_edge": -0.02}},
        },
    }), encoding="utf-8")
    (runtime / "strategy_claims.json").write_text(json.dumps({
        "claims": {
            "claim-1": {
                "claim": {"raw_excerpt": "Long BTC breakout"},
                "falsifiability": {"falsifiable": True},
                "interpretation_count": 4,
                "reproducibility": {"status": "NOT_YET_BACKTESTED"},
            },
            "claim-2": {
                "claim": {"raw_excerpt": "trust me"},
                "falsifiability": {"falsifiable": False},
            },
        },
    }), encoding="utf-8")
    (runtime / "no_edge_map.json").write_text(json.dumps({
        "scopes": {
            "src|btc|market|1h": {"verdict": "insufficient"},
            "src|mlb|na|pre": {"verdict": "edge"},
        },
    }), encoding="utf-8")

    board = build_recruiting_board(runtime=runtime)
    types = {p["source_type"] for p in board["prospects"]}
    assert "mined_rule" in types and "compiled_claim" in types
    # FORWARD_POSITIVE mined rule is COMMITTED and ranks above the PROSPECT claim.
    assert board["prospects"][0]["stage"] in ("STARTER", "COMMITTED")
    # Unfalsifiable claim never makes the board.
    assert all("trust me" not in p["name"] for p in board["prospects"])
    # CUT (forward-negative) prospects sink to the bottom.
    assert board["prospects"][-1]["stage"] == "CUT"
    assert {"scope": "src|btc|market|1h", "need": "insufficient_evidence"} in board["position_needs"]
    assert board["by_stage"].get("CUT") == 1
