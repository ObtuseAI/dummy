"""Wave-84 Bug 2: a busy competing writer must degrade the signal write, not
kill the cycle.

Live evidence (runtime/autonomy/cycles.jsonl, three CYCLE_ERROR:OperationalError
cycles on 2026-07-24)::

    File "autonomy/brain.py", line 826, in run_cycle
        accepted_mask = self.ledger.record_signals(signals)
    File "autonomy/ledger.py", line 650, in record_signals
        cursor = self._conn.execute(
    sqlite3.OperationalError: database is locked

WAL removed reader-vs-writer blocking; this is the writer-vs-writer remainder.
A competitor (retention / signal_prune / out-of-band recal) held the single WAL
write lock past busy_timeout, and the cycle's *observational* signal write took
the decide/execute/persist stages down with it.

Every lock here is a real one: a second sqlite connection holding
``BEGIN IMMEDIATE`` on the same database. Nothing under test is mocked.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import autonomy.ledger as ledger_mod
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal


@pytest.fixture(autouse=True)
def _fast_lock_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the suite hermetic and fast: real locks, tiny waits.

    Production waits ~60s per statement inside a 120s budget; the mechanism is
    identical at 50ms/200ms, and the constants are read at call time.
    """
    monkeypatch.setattr(ledger_mod, "LEDGER_BUSY_TIMEOUT_S", 0.05)
    monkeypatch.setattr(ledger_mod, "LEDGER_SIGNAL_LOCK_BUDGET_S", 0.2)
    monkeypatch.setattr(ledger_mod, "LEDGER_SIGNAL_LOCK_COOLDOWN_S", 0.0)
    monkeypatch.setattr(ledger_mod, "LEDGER_LOCK_BACKOFF_S", 0.01)


def _sig(source: str, ticker: str, features: dict | None = None) -> Signal:
    return Signal(
        source=source,
        market_ticker=ticker,
        probability_yes=0.5,
        uncertainty=0.1,
        rationale="",
        created_at="2026-01-01T00:00:01+00:00",
        features=features or {},
    )


def _rows(ledger: AutonomyLedger) -> int:
    return ledger._conn.execute(  # noqa: SLF001 - direct row assertion
        "SELECT COUNT(*) FROM signals"
    ).fetchone()[0]


def _blocker(db_path: Path) -> sqlite3.Connection:
    """A second real writer, exactly like retention/prune on the live box."""
    return sqlite3.connect(str(db_path), timeout=0.05)


def _hold_write_lock_before_insert(
    ledger: AutonomyLedger, blocker: sqlite3.Connection, *, nth_insert: int,
) -> dict:
    """Take the WAL write lock just before the Nth signal INSERT.

    sqlite's trace hook fires as a statement starts, i.e. in the window after a
    chunk COMMIT released the write lock and before the next INSERT re-takes
    it. That makes "competitor arrives mid-write" deterministic instead of a
    thread race, without touching the code under test.
    """
    state = {"inserts": 0, "held": False}

    def _trace(sql: str) -> None:
        if not sql.strip().upper().startswith("INSERT INTO SIGNALS"):
            return
        state["inserts"] += 1
        if state["inserts"] == nth_insert and not state["held"]:
            try:
                blocker.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError:  # pragma: no cover - lock already held
                return
            state["held"] = True

    ledger._conn.set_trace_callback(_trace)  # noqa: SLF001 - sqlite hook, not a mock
    return state


def test_ledger_runs_in_wal_so_this_is_a_writer_vs_writer_test(tmp_path: Path) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        assert ledger._conn.execute(  # noqa: SLF001
            "PRAGMA journal_mode"
        ).fetchone()[0].lower() == "wal"
    finally:
        ledger.close()


def test_signal_write_degrades_partially_instead_of_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ledger_mod, "LEDGER_SIGNAL_WRITE_CHUNK", 2)
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    blocker = _blocker(db)
    try:
        state = _hold_write_lock_before_insert(ledger, blocker, nth_insert=3)
        signals = [_sig(f"s{i}", f"MKT{i}") for i in range(6)]

        accepted = ledger.record_signals(signals)  # must return, not raise

        ledger._conn.set_trace_callback(None)  # noqa: SLF001
        assert state["held"] is True
        # First chunk committed before the competitor arrived and stays
        # durable; everything from the abandoned chunk on is reported unwritten
        # so signals_generated/signals_rejected degrade honestly.
        assert accepted == [True, True, False, False, False, False]
        assert _rows(ledger) == 2
        health = ledger.health()
        assert health["signal_rows_dropped_lock"] == 4
        assert health["signal_drop_episodes"] == 1
        assert health["last_signal_drop"]["reason"] == "lock_signal_write"
        assert "rollback_error" not in health["last_signal_drop"]
    finally:
        blocker.rollback()
        blocker.close()
        ledger.close()


def test_whole_batch_degrades_when_the_lock_is_held_from_the_start(
    tmp_path: Path,
) -> None:
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    blocker = _blocker(db)
    try:
        blocker.execute("BEGIN IMMEDIATE")

        accepted = ledger.record_signals([_sig(f"s{i}", f"MKT{i}") for i in range(3)])

        assert accepted == [False, False, False]
        assert _rows(ledger) == 0
        assert ledger.health()["signal_rows_dropped_lock"] == 3
    finally:
        blocker.rollback()
        blocker.close()
        ledger.close()


def test_normal_write_is_fully_accepted_once_the_competitor_releases(
    tmp_path: Path,
) -> None:
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    blocker = _blocker(db)
    try:
        blocker.execute("BEGIN IMMEDIATE")
        assert ledger.record_signals([_sig("s0", "MKT0")]) == [False]

        blocker.rollback()  # competitor finished

        accepted = ledger.record_signals([_sig(f"s{i}", f"MKT{i}") for i in range(4)])
        assert accepted == [True] * 4
        assert _rows(ledger) == 4
        # The drop episode stays on the record; recovery does not erase it.
        assert ledger.health()["signal_drop_episodes"] == 1
    finally:
        blocker.close()
        ledger.close()


def test_all_or_none_replay_raises_and_writes_nothing(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    blocker = _blocker(db)
    try:
        blocker.execute("BEGIN IMMEDIATE")

        # Replay atomicity outranks availability: a half-written baseline/model
        # pair is worse than a loud failure.
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            ledger.record_signals(
                [_sig("s0", "MKT0"), _sig("s1", "MKT1")],
                mode="retro",
                all_or_none=True,
            )

        blocker.rollback()
        assert _rows(ledger) == 0
        assert ledger.health()["last_signal_drop"]["reason"] == "lock_all_or_none"
    finally:
        blocker.close()
        ledger.close()


def test_rolled_back_tier_epoch_is_not_remembered_as_written(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    blocker = _blocker(db)
    try:
        blocker.execute("BEGIN IMMEDIATE")
        fused = [
            _sig(
                "fused_forecast", "MKT0",
                features={"tier_policy_version": "executable_value_v5"},
            )
        ]
        assert ledger.record_signals(fused) == [False]

        blocker.rollback()
        assert ledger.record_signals(fused) == [True]

        # The epoch row must exist: an in-memory "already seen" left over from
        # the rolled-back attempt would suppress this INSERT forever.
        assert ledger._conn.execute(  # noqa: SLF001
            "SELECT COUNT(*) FROM tier_policy_epochs WHERE policy_version=?",
            ("executable_value_v5",),
        ).fetchone()[0] == 1
    finally:
        blocker.close()
        ledger.close()


def test_drop_cooldown_fast_fails_further_signal_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ledger_mod, "LEDGER_SIGNAL_LOCK_COOLDOWN_S", 30.0)
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    blocker = _blocker(db)
    try:
        blocker.execute("BEGIN IMMEDIATE")
        assert ledger.record_signals([_sig("s0", "MKT0")]) == [False]
        blocker.rollback()

        # Still inside the cooldown: the cycle spends its remaining seconds
        # trading instead of re-queueing behind the same competitor once per
        # market. The drop stays counted, never silent.
        assert ledger.record_signals([_sig("s1", "MKT1")]) == [False]
        assert ledger.health()["last_signal_drop"]["reason"] == "lock_cooldown"
        assert ledger.health()["signal_rows_dropped_lock"] == 2

        ledger._signal_lock_cooldown_until = 0.0  # noqa: SLF001 - window elapsed
        assert ledger.record_signals([_sig("s2", "MKT2")]) == [True]
    finally:
        blocker.close()
        ledger.close()


def test_lock_budget_outlasts_the_plain_attempt_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The deadline budget must not inherit LEDGER_LOCK_RETRIES' ~1.6s ceiling."""
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    monkeypatch.setattr(ledger_mod.time, "sleep", lambda _s: None)
    try:
        calls = {"n": 0}

        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] <= ledger_mod.LEDGER_LOCK_RETRIES + 3:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        deadline = ledger_mod.time.monotonic() + 30.0
        assert ledger._retry_on_locked(flaky, deadline=deadline) == "ok"  # noqa: SLF001
        assert calls["n"] > ledger_mod.LEDGER_LOCK_RETRIES
    finally:
        ledger.close()


def test_non_lock_errors_still_propagate_immediately(tmp_path: Path) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        calls = {"n": 0}

        def broken() -> None:
            calls["n"] += 1
            raise sqlite3.OperationalError("no such table: nope")

        deadline = ledger_mod.time.monotonic() + 30.0
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            ledger._retry_on_locked(broken, deadline=deadline)  # noqa: SLF001
        assert calls["n"] == 1  # fail-closed, never retried
    finally:
        ledger.close()
