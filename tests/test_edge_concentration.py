"""Edge-concentration audit flags narrow, likely-artifact edges."""
from __future__ import annotations

import sqlite3

from autonomy.edge_concentration import build_edge_concentration


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


def _add(conn, source, ticker, model_p, market_p, result, mt):
    for s, p in ((source, model_p), ("market_prior", market_p)):
        conn.execute(
            "INSERT INTO signals(source, market_ticker, probability_yes, uncertainty,"
            " rationale, created_at, mode, features, ingested_at, ingest_version)"
            " VALUES (?,?,?,0.1,'', datetime('now'),'live',?, '',2)",
            (s, ticker, p, f'{{"market_type": "{mt}"}}'),
        )
    conn.execute("INSERT OR IGNORE INTO settlements VALUES (?,?)", (ticker, result))


def test_diversified_edge_is_not_flagged():
    conn = _db()
    # Sharp across 3 market types and many events -> low concentration.
    for i in range(60):
        mt = ("winner", "spread", "total")[i % 3]
        result = i % 2
        model_p = 0.85 if result else 0.15   # confident + correct
        _add(conn, "good", f"KXNBAGAME-26JAN{i:02d}AB-A", model_p, 0.5, result, mt)
    report = build_edge_concentration(conn, days=None)
    (row,) = [s for s in report["sources"] if s["source"] == "good"]
    assert row["positive_market_types"] >= 2
    assert row["narrow_edge_warning"] is False
    assert "good" not in report["narrow_edge_sources"]


def test_single_market_type_edge_is_flagged():
    conn = _db()
    for i in range(60):
        result = i % 2
        model_p = 0.85 if result else 0.15
        # All edge in ONE market type -> HHI ~1.
        _add(conn, "narrow", f"KXNBAGAME-26FEB{i:02d}AB-A", model_p, 0.5, result, "winner")
    report = build_edge_concentration(conn, days=None)
    (row,) = [s for s in report["sources"] if s["source"] == "narrow"]
    assert row["market_type_hhi"] > 0.6
    assert "edge_concentrated_in_one_market_type" in row["warnings"]
    assert "narrow" in report["narrow_edge_sources"]


def test_below_min_rows_is_excluded():
    conn = _db()
    for i in range(10):
        _add(conn, "thin", f"KXNBAGAME-26MAR{i:02d}AB-A", 0.8, 0.5, 1, "winner")
    report = build_edge_concentration(conn, days=None)
    assert all(s["source"] != "thin" for s in report["sources"])
