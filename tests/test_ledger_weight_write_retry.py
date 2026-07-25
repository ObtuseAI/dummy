"""The statement that takes the write lock must be the one that retries.

Production, 2026-07-25: run_backtest's weight loop died 185s in at
update_weight's INSERT with sqlite3.OperationalError "database is locked",
against a confirmed 600000ms busy_timeout on a WAL database.

update_weight retried only ``commit``. In WAL the write lock is acquired by the
first DML statement, not by COMMIT, so the retry guarded an operation that was
never the one refused while the INSERT that actually contends had none.
"""
from __future__ import annotations

import sqlite3

import pytest

from autonomy.ledger import AutonomyLedger


class _FlakyConn:
    """Delegates to a real connection, refusing the first N INSERTs."""

    def __init__(self, conn, fail_inserts: int, forever: bool = False):
        self._conn = conn
        self._remaining = fail_inserts
        self._forever = forever
        self.insert_attempts = 0

    def execute(self, sql, *args, **kwargs):
        if sql.lstrip().upper().startswith("INSERT"):
            self.insert_attempts += 1
            if self._forever or self._remaining > 0:
                self._remaining -= 1
                raise sqlite3.OperationalError("database is locked")
        return self._conn.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_update_weight_retries_the_locked_insert(tmp_path):
    led = AutonomyLedger(db_path=tmp_path / "ledger.db")
    real = led._conn
    try:
        led._conn = _FlakyConn(real, fail_inserts=2)

        led.update_weight("crypto_patience_confirm", 1.635)

        assert led._conn.insert_attempts == 3, "must retry past a transient lock"
        led._conn = real
        row = real.execute(
            "SELECT weight FROM source_trust WHERE source=?",
            ("crypto_patience_confirm",),
        ).fetchone()
        assert row is not None and abs(float(row[0]) - 1.635) < 1e-9
    finally:
        led._conn = real
        led.close()


def test_update_weight_still_propagates_a_persistent_lock(tmp_path, monkeypatch):
    """Bounded by wall clock, fail-closed -- never an infinite spin.

    The budget is injected rather than waited out: the production value is two
    minutes, which is the point (a competing writer can hold the WAL write lock
    far longer than the five-attempt backoff covers), but a test must not sleep
    through it.
    """
    import autonomy.ledger as ledger_module

    monkeypatch.setattr(ledger_module, "WEIGHT_WRITE_LOCK_BUDGET_S", 0.3)
    led = AutonomyLedger(db_path=tmp_path / "ledger.db")
    real = led._conn
    try:
        led._conn = _FlakyConn(real, fail_inserts=0, forever=True)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            led.update_weight("s", 1.0)
    finally:
        led._conn = real
        led.close()


def test_weight_write_budget_outlasts_the_measured_contention(tmp_path):
    """The budget must comfortably exceed what production actually blocked.

    A measured recalibration blocked 3.742s on its first weight write. The
    five-attempt backoff covers only ~3.1s, so the attempt bound decided that
    run by a fraction of a second. Pin a budget with real headroom.
    """
    import autonomy.ledger as ledger_module

    assert ledger_module.WEIGHT_WRITE_LOCK_BUDGET_S >= 30.0
