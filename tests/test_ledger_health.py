"""Ledger concurrency hardening + health probes.

Regression anchor: the live daemon heartbeat showed
``CYCLE_ERROR:OperationalError`` with ``error: "database is locked"`` while the
ledger sat at 9.25 GiB — writers raced the 6-hourly recalibration's long reads
with SQLite's default 5s lock wait and no retry. The ledger now waits
(busy_timeout), retries commits within a bound, and exposes read-only health
probes for the heartbeat/alert surfaces.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import autonomy.ledger as ledger_mod
from autonomy.ledger import (
    LEDGER_BUSY_TIMEOUT_S,
    LEDGER_LOCK_RETRIES,
    AutonomyLedger,
    ledger_health_probe,
)


def test_connection_waits_for_locks_instead_of_failing_fast(tmp_path: Path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        timeout_ms = int(ledger._conn.execute("PRAGMA busy_timeout").fetchone()[0])  # noqa: SLF001
        assert timeout_ms == int(LEDGER_BUSY_TIMEOUT_S * 1000)
    finally:
        ledger.close()


def test_retry_on_locked_retries_lock_errors_within_bound(tmp_path: Path, monkeypatch):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    monkeypatch.setattr(ledger_mod.time, "sleep", lambda _s: None)
    try:
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        assert ledger._retry_on_locked(flaky) == "ok"  # noqa: SLF001
        assert calls["n"] == 3
        assert ledger.health()["lock_retries"] == 2
    finally:
        ledger.close()


def test_retry_on_locked_gives_up_after_bound(tmp_path: Path, monkeypatch):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    monkeypatch.setattr(ledger_mod.time, "sleep", lambda _s: None)
    try:
        calls = {"n": 0}

        def always_locked():
            calls["n"] += 1
            raise sqlite3.OperationalError("database is locked")

        with pytest.raises(sqlite3.OperationalError):
            ledger._retry_on_locked(always_locked)  # noqa: SLF001
        assert calls["n"] == LEDGER_LOCK_RETRIES  # bounded, never infinite
    finally:
        ledger.close()


def test_retry_on_locked_propagates_non_lock_errors_immediately(tmp_path: Path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        calls = {"n": 0}

        def corrupt():
            calls["n"] += 1
            raise sqlite3.OperationalError("no such table: nonsense")

        with pytest.raises(sqlite3.OperationalError):
            ledger._retry_on_locked(corrupt)  # noqa: SLF001
        assert calls["n"] == 1  # a non-lock error is never retried
    finally:
        ledger.close()


def test_writes_survive_a_transient_writer_lock(tmp_path: Path):
    """End-to-end: a commit that hits a locked database succeeds once the
    other writer releases within the busy timeout."""
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    try:
        ledger.update_weight("a_x", 1.5)
        assert ledger.get_weight("a_x") == 1.5
    finally:
        ledger.close()


def test_health_snapshot_reports_size_and_journal(tmp_path: Path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        info = ledger.health()
        assert info["size_bytes"] > 0
        assert info["bloat_warn"] is False
        assert str(info["journal_mode"]).lower() == "wal"  # Wave-83 concurrency contract
        assert info["lock_retries"] == 0
    finally:
        ledger.close()


def test_health_bloat_warn_threshold(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ledger_mod, "LEDGER_BLOAT_WARN_BYTES", 1)
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        assert ledger.health()["bloat_warn"] is True
    finally:
        ledger.close()


def test_integrity_check_quick_and_full(tmp_path: Path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        assert ledger.integrity_check(quick=True) == {
            "ok": True, "quick": True, "result": ["ok"],
        }
        assert ledger.integrity_check(quick=False)["ok"] is True
    finally:
        ledger.close()


def test_probe_missing_db_is_a_clean_finding(tmp_path: Path):
    info = ledger_health_probe(tmp_path / "absent.db")
    assert info["exists"] is False
    assert info["probe_error"] is None
    assert info["bloat_warn"] is False
    assert not (tmp_path / "absent.db").exists()  # probing never creates


def test_probe_reads_existing_db_read_only(tmp_path: Path):
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    ledger.close()
    before = db.stat().st_mtime_ns
    info = ledger_health_probe(db)
    assert info["exists"] is True
    assert info["size_bytes"] > 0
    assert info["probe_error"] is None
    assert str(info["journal_mode"]).lower() == "wal"
    assert db.stat().st_mtime_ns == before  # untouched


def test_probe_failure_is_reported_not_raised(tmp_path: Path):
    bogus = tmp_path / "bogus.db"
    bogus.write_text("this is not a sqlite database " * 30, encoding="utf-8")
    info = ledger_health_probe(bogus)
    assert info["exists"] is True
    assert info["probe_error"] is not None  # a sick DB is a finding, not a crash


def test_probe_flags_bloat(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ledger_mod, "LEDGER_BLOAT_WARN_BYTES", 1)
    db = tmp_path / "ledger.db"
    AutonomyLedger(db).close()
    assert ledger_health_probe(db)["bloat_warn"] is True


def test_daemon_heartbeat_carries_ledger_health(monkeypatch, tmp_path: Path):
    import json

    import autonomy.daemon as daemon
    from autonomy.ontology import SessionMode

    monkeypatch.setattr(daemon, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(daemon, "HEARTBEAT_PATH", tmp_path / "hb.json")
    monkeypatch.setattr(daemon, "CYCLE_LOG_PATH", tmp_path / "c.jsonl")
    monkeypatch.setattr(daemon, "kill_switch_active", lambda: False)
    AutonomyLedger(tmp_path / "ledger.db").close()

    class FakeReport:
        def to_dict(self):
            return {"status": "CYCLE_OK", "settlements": 0}

    class FakeBrain:
        class _L:
            def close(self):
                pass

        ledger = _L()

        async def run_cycle(self):
            return FakeReport()

    monkeypatch.setattr("autonomy.session.build_brain", lambda m: FakeBrain())
    daemon.run_one_cycle("2026-07-16T00:00:00+00:00", SessionMode.SHADOW)
    heartbeat = json.loads((tmp_path / "hb.json").read_text(encoding="utf-8"))
    health = heartbeat["ledger_health"]
    assert health["exists"] is True
    assert health["size_bytes"] > 0
    assert health["probe_error"] is None
