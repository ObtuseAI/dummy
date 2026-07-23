"""Paired quant-vs-LLM value report: honest paired design, report-only."""
from __future__ import annotations

import sqlite3

from autonomy.llm_value_report import build_llm_value_report
from autonomy.picks import llm_voice_sources


VOICE = "llm_panel_v3_claude_sonnet_5_abc123"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE signal_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT, market_ticker TEXT,
            probability_yes REAL, created_at TEXT
        );
        CREATE TABLE settlements(market_ticker TEXT PRIMARY KEY, result_yes INTEGER);
        """
    )
    return conn


def _seed(conn: sqlite3.Connection, n: int = 24) -> None:
    for i in range(n):
        # Distinct events -> distinct clusters (group_key falls back per ticker).
        ticker = f"KXMLBGAME-26JUL{i:02d}AAABBB-AAA"
        result = i % 2 == 0
        # Voice is sharper than fused; fused sharper than market.
        voice_p = 0.9 if result else 0.1
        fused_p = 0.7 if result else 0.3
        market_p = 0.55 if result else 0.45
        for source, prob in (
            (VOICE, voice_p), ("fused_forecast", fused_p), ("market_prior", market_p),
        ):
            conn.execute(
                "INSERT INTO signal_history(source, market_ticker, probability_yes,"
                " created_at) VALUES (?,?,?,datetime('now'))",
                (source, ticker, prob),
            )
        conn.execute(
            "INSERT INTO settlements(market_ticker, result_yes) VALUES (?,?)",
            (ticker, 1 if result else 0),
        )
    conn.commit()


def test_voice_discovery_finds_settled_llm_sources():
    conn = _db()
    _seed(conn)
    assert llm_voice_sources(conn) == (VOICE,)


def test_paired_report_grades_voice_against_fused_and_market():
    conn = _db()
    _seed(conn)
    report = build_llm_value_report(conn)
    assert report["authority"] == "report_only_no_probability_or_execution_authority"
    (row,) = report["voices"]
    assert row["status"] == "OK"
    assert row["paired_rows"] == 24
    assert row["voice_brier"] < row["fused_brier"]
    low, high = row["brier_advantage_vs_fused_ci95"]
    assert low > 0.0 and high >= low
    assert row["adds_value_over_fused"] is True


def test_insufficient_rows_disclose_instead_of_scoring():
    conn = _db()
    _seed(conn, n=4)
    report = build_llm_value_report(conn)
    (row,) = report["voices"]
    assert row["status"] == "INSUFFICIENT_PAIRED_ROWS"
    assert row["paired_rows"] == 4


def test_no_voices_yields_empty_report():
    conn = _db()
    report = build_llm_value_report(conn)
    assert report["voices"] == []
