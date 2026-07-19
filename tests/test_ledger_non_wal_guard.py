"""Wave-41: guard the ledger's non-WAL invariant.

The recurring "database is locked" contention was NOT fixed with WAL: WAL would
break retention.enforce_retention (which needs an atomic archive+delete across
the attached archive DB and hard-refuses under WAL), and would let the already
16 GB ledger grow forever. The real fix is running retention. These tests pin
the invariant so a future change can't silently flip the ledger to WAL and
break archival.
"""
from __future__ import annotations

import sqlite3

import pytest

from autonomy.ledger import AutonomyLedger
from autonomy.retention import enforce_retention


def test_fresh_ledger_is_not_wal(tmp_path):
    led = AutonomyLedger(tmp_path / "ledger.db")
    try:
        mode = str(led._conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    finally:
        led.close()
    assert mode != "wal"   # WAL breaks the atomic archive+delete retention needs


def test_retention_apply_refuses_wal(tmp_path):
    db = tmp_path / "ledger.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE signals(id INTEGER PRIMARY KEY, market_ticker TEXT, "
        "created_at TEXT, settled_at TEXT, outcome TEXT)")
    # Retention computes eligibility (joining settlements) before the WAL check.
    conn.execute("CREATE TABLE settlements(market_ticker TEXT, settled_at TEXT)")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="WAL"):
        enforce_retention(db, apply=True, retention_days=1.0)
