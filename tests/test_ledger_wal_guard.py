"""Wave-83: guard the ledger's WAL invariant.

Wave-41 pinned the opposite (non-WAL) because retention.enforce_retention then
required a single atomic cross-database archive+delete transaction. That
requirement was removed by the two-phase idempotent retention protocol, and
rollback-journal mode caused the 2026-07-24 production lockout (a multi-hour
reader starved a writer at PENDING, which then locked out every new reader).
These tests pin WAL so a future change can't silently reintroduce
reader/writer blocking, and pin that retention apply works under WAL.
"""
from __future__ import annotations

import sqlite3

from autonomy.ledger import AutonomyLedger
from autonomy.retention import enforce_retention


def test_fresh_ledger_is_wal(tmp_path):
    led = AutonomyLedger(tmp_path / "ledger.db")
    try:
        mode = str(led._conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    finally:
        led.close()
    assert mode == "wal"  # readers and writers must never block each other


def test_ledger_wal_env_escape(tmp_path, monkeypatch):
    monkeypatch.setenv("DUMMY_LEDGER_WAL", "0")
    led = AutonomyLedger(tmp_path / "ledger.db")
    try:
        mode = str(led._conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    finally:
        led.close()
    assert mode != "wal"


def test_retention_apply_works_on_wal_ledger(tmp_path):
    db = tmp_path / "ledger.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE signals(id INTEGER PRIMARY KEY,source TEXT NOT NULL,"
        "market_ticker TEXT NOT NULL,probability_yes REAL NOT NULL,"
        "uncertainty REAL NOT NULL,rationale TEXT NOT NULL,created_at TEXT NOT NULL,"
        "mode TEXT NOT NULL,features TEXT NOT NULL,ingested_at TEXT NOT NULL,"
        "ingest_version INTEGER NOT NULL)"
    )
    conn.execute("CREATE TABLE settlements(market_ticker TEXT PRIMARY KEY, settled_at TEXT)")
    conn.execute(
        "INSERT INTO signals VALUES (1,'model_a','OLD',0.5,0.1,'r',"
        "'2026-07-01T00:00:00+00:00','live','{}','2026-07-01T00:00:00+00:00',2)"
    )
    conn.execute("INSERT INTO settlements VALUES ('OLD','2026-07-02T00:00:00+00:00')")
    conn.commit()
    conn.close()

    report = enforce_retention(db, apply=True, retention_days=1.0)

    assert report.status == "APPLIED"
    assert report.archived_rows == 1
    check = sqlite3.connect(db)
    try:
        assert check.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 0
    finally:
        check.close()


def test_statement_deadline_interrupts_long_query(tmp_path):
    """The progress handler must abort a statement running past the deadline —
    the mechanism that makes the cycle deadline enforceable against sync SQL."""
    import time as _time

    import pytest

    led = AutonomyLedger(tmp_path / "ledger.db")
    try:
        led._conn.execute(
            "WITH RECURSIVE seed(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM seed LIMIT 20000) "
            "INSERT INTO signals(source,market_ticker,probability_yes,uncertainty,rationale,"
            "created_at,mode,features,ingested_at,ingest_version) "
            "SELECT 'perf','T'||x,0.5,0.1,'r','2026-07-01T00:00:00+00:00','live','{}',"
            "'2026-07-01T00:00:00+00:00',2 FROM seed"
        )
        led._conn.commit()
        led.set_statement_deadline(_time.monotonic() + 0.05)
        with pytest.raises(sqlite3.OperationalError, match="interrupt"):
            # Cross join is quadratic — far more than 0.05s of work.
            led._conn.execute(
                "SELECT COUNT(*) FROM signals a, signals b WHERE a.rationale=b.rationale"
            ).fetchone()
        led.set_statement_deadline(None)
        # Cleared deadline: statements run normally again.
        assert led._conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 20000
    finally:
        led.close()
