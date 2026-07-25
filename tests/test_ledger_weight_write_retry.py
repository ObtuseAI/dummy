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


def test_update_weight_fails_fast_inside_a_watchdog_bounded_cycle(tmp_path):
    """The per-write path must NOT inherit the batch's wall-clock budget.

    autonomy/learner.py calls update_weight several times inside every cycle,
    and a 13-minute watchdog bounds those. Giving this path the two-minute batch
    budget made a contended learner write stall where it used to give up in
    about three seconds, and cycles began dying on CYCLE_ERROR:CycleDeadline.
    Five attempts over ~3.1s of backoff is the correct bound here; the patience
    belongs to update_weights, which runs out of band.
    """
    import time as _time

    led = AutonomyLedger(db_path=tmp_path / "ledger.db")
    real = led._conn
    try:
        led._conn = _FlakyConn(real, fail_inserts=0, forever=True)
        t0 = _time.monotonic()
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            led.update_weight("s", 1.0)
        elapsed = _time.monotonic() - t0
        assert elapsed < 30.0, (
            f"per-write retry took {elapsed:.1f}s; it must fail fast inside a cycle"
        )
    finally:
        led._conn = real
        led.close()


def test_update_weight_still_propagates_a_persistent_lock(tmp_path):
    """Bounded retry, fail-closed -- never an infinite spin."""
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


class _CountingConn:
    """Delegates to a real connection, counting lock acquisitions."""

    def __init__(self, conn, fail_begins: int = 0):
        self._conn = conn
        self._fail_begins = fail_begins
        self.begins = 0
        self.commits = 0

    def execute(self, sql, *args, **kwargs):
        if sql.strip().upper().startswith("BEGIN"):
            self.begins += 1
            if self._fail_begins > 0:
                self._fail_begins -= 1
                raise sqlite3.OperationalError("database is locked")
        return self._conn.execute(sql, *args, **kwargs)

    def commit(self):
        self.commits += 1
        return self._conn.commit()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_batch_weight_write_takes_the_lock_once(tmp_path):
    """478 weights must be 1 acquisition, not 478.

    Per-source commits gave a continuously-writing competitor 478 independent
    chances to abort a 390s recalibration.
    """
    led = AutonomyLedger(db_path=tmp_path / "ledger.db")
    real = led._conn
    try:
        led._conn = _CountingConn(real)
        weights = {f"source_{i}": 1.0 + i / 1000.0 for i in range(478)}

        led.update_weights(weights)

        assert led._conn.begins == 1, "the batch must acquire the write lock once"
        assert led._conn.commits == 1, "and commit once"
        led._conn = real
        stored = dict(real.execute("SELECT source, weight FROM source_trust").fetchall())
        assert len(stored) == 478
        assert abs(stored["source_477"] - 1.477) < 1e-9
    finally:
        led._conn = real
        led.close()


def test_batch_weight_write_retries_a_locked_acquisition(tmp_path):
    led = AutonomyLedger(db_path=tmp_path / "ledger.db")
    real = led._conn
    try:
        led._conn = _CountingConn(real, fail_begins=2)

        led.update_weights({"crypto_patience_confirm": 1.635})

        assert led._conn.begins == 3, "must retry a refused acquisition"
        led._conn = real
        row = real.execute(
            "SELECT weight FROM source_trust WHERE source=?",
            ("crypto_patience_confirm",),
        ).fetchone()
        assert row is not None and abs(float(row[0]) - 1.635) < 1e-9
    finally:
        led._conn = real
        led.close()


def test_batch_weight_write_is_a_noop_for_empty_input(tmp_path):
    led = AutonomyLedger(db_path=tmp_path / "ledger.db")
    real = led._conn
    try:
        led._conn = _CountingConn(real)
        led.update_weights({})
        assert led._conn.begins == 0
    finally:
        led._conn = real
        led.close()
