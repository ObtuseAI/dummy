"""Fusion ablation: marginal contribution ranking, redundancy detection."""
from __future__ import annotations

import json
import sqlite3


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


def _emit(conn, source, ticker, prob, unc=0.1):
    conn.execute(
        "INSERT INTO signals(source, market_ticker, probability_yes, uncertainty,"
        " rationale, created_at, mode, features, ingested_at, ingest_version)"
        " VALUES (?,?,?,?,'', datetime('now'),'live','{}','',2)",
        (source, ticker, prob, unc),
    )


def _settle(conn, ticker, result):
    conn.execute("INSERT OR IGNORE INTO settlements VALUES (?,?)", (ticker, result))


def test_informative_source_ranks_above_redundant_noise(tmp_path):
    from autonomy.fusion_ablation import build_fusion_ablation

    conn = _db()
    recal = tmp_path / "recal.json"
    recal.write_text(json.dumps({"weights": {}}), encoding="utf-8")
    # 40 markets, distinct clusters. "sharp" alone knows the outcome; "noise_a"
    # and "noise_b" always say 0.5 (identical -> mutually redundant).
    for i in range(40):
        ticker = f"KXE-{i:03d}A-T1"
        result = i % 2 == 0
        _emit(conn, "sharp", ticker, 0.9 if result else 0.1)
        _emit(conn, "noise_a", ticker, 0.5)
        _emit(conn, "noise_b", ticker, 0.5)
        _settle(conn, ticker, 1 if result else 0)
    report = build_fusion_ablation(conn, days=None, recal_path=recal)
    by = {s["source"]: s for s in report["sources"]}
    assert by["sharp"]["adds_information"] is True
    assert by["sharp"]["marginal_brier_contribution"] > 0.01
    # Removing one 0.5-sayer leaves the other: zero marginal value.
    assert by["noise_a"]["redundant_or_harmful"] is True
    assert "noise_a" in report["redundancy_candidates"]
    assert report["sources"][0]["source"] == "sharp"
    assert report["markets_used"] == 40


def test_markets_below_source_floor_are_excluded(tmp_path):
    from autonomy.fusion_ablation import build_fusion_ablation

    conn = _db()
    recal = tmp_path / "recal.json"
    recal.write_text(json.dumps({"weights": {}}), encoding="utf-8")
    # Only 5 markets -> below MIN_MARKETS_PER_SOURCE -> no verdicts.
    for i in range(5):
        ticker = f"KXF-{i:03d}A-T1"
        for src in ("a", "b", "c"):
            _emit(conn, src, ticker, 0.6)
        _settle(conn, ticker, 1)
    report = build_fusion_ablation(conn, days=None, recal_path=recal)
    assert report["sources"] == []


def test_two_source_markets_skipped(tmp_path):
    from autonomy.fusion_ablation import build_fusion_ablation

    conn = _db()
    recal = tmp_path / "recal.json"
    recal.write_text(json.dumps({"weights": {}}), encoding="utf-8")
    for i in range(40):
        ticker = f"KXG-{i:03d}A-T1"
        _emit(conn, "a", ticker, 0.7)
        _emit(conn, "b", ticker, 0.6)
        _settle(conn, ticker, 1)
    report = build_fusion_ablation(conn, days=None, recal_path=recal)
    assert report["markets_used"] == 0
