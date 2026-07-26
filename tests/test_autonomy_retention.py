from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal
from autonomy.retention import (
    default_archive_path,
    enforce_retention,
    ensure_signal_history,
)
from autonomy.strategy_miner import load_settled_rows


NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)


def _signal(ticker: str, source: str, created_at: str) -> Signal:
    return Signal(
        source=source,
        market_ticker=ticker,
        probability_yes=0.61,
        uncertainty=0.12,
        rationale="retention fixture",
        created_at=created_at,
        features={"fixture": True},
    )


def _fixture_ledger(path: Path) -> None:
    ledger = AutonomyLedger(path)
    try:
        assert ledger.record_signal(_signal("OLD", "model_a", "2026-07-01T10:00:00+00:00"))
        assert ledger.record_signal(_signal("OLD", "market_prior", "2026-07-01T10:00:01+00:00"))
        assert ledger.record_signal(_signal("RECENT", "model_a", "2026-07-12T10:00:00+00:00"))
        assert ledger.record_signal(_signal("OPEN", "model_a", "2026-06-30T10:00:00+00:00"))
        ledger._conn.execute(  # noqa: SLF001
            "INSERT INTO settlements VALUES (?,?,?)", ("OLD", 1, "2026-07-02T00:00:00+00:00")
        )
        ledger._conn.execute(  # noqa: SLF001
            "INSERT INTO settlements VALUES (?,?,?)", ("RECENT", 0, "2026-07-12T12:00:00+00:00")
        )
        ledger._conn.execute(  # noqa: SLF001
            "INSERT INTO decisions(decision_id,market_ticker,action,side,price_cents,count,ev_cents,"
            "kelly,notional_cents,probability_yes,forecast_uncertainty,market_implied_yes,"
            "sources_used,abstain_reason,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "D1", "OLD", "ABSTAIN", "yes", 50, 0, 0.0, 0.0, 0, 0.61, 0.12,
                0.5, "{}", "fixture", "2026-07-01T10:00:02+00:00",
            ),
        )
        ledger._conn.commit()  # noqa: SLF001
    finally:
        ledger.close()


def test_retention_dry_run_is_non_mutating(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _fixture_ledger(db)
    archive = default_archive_path(db)

    report = enforce_retention(db, retention_days=7, now=NOW)

    assert report.status == "DRY_RUN"
    assert report.eligible_rows == 2
    assert report.archived_rows == 0
    assert report.source_rows_before == report.source_rows_after == 4
    assert not archive.exists()


def test_retention_preserves_full_history_and_non_signal_truth(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _fixture_ledger(db)
    before = sqlite3.connect(db)
    try:
        settled_before = load_settled_rows(before)
    finally:
        before.close()

    report = enforce_retention(
        db, retention_days=7, apply=True, batch_size=1, now=NOW,
    )

    assert report.status == "APPLIED"
    assert report.archived_rows == 2
    assert report.batches == 2
    assert report.source_rows_before == 4
    assert report.source_rows_after == 2
    assert report.history_rows_after == 4
    assert report.execution_authority is False
    assert report.tables_mutated == ("signals",)

    hot = sqlite3.connect(db)
    try:
        assert hot.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 2
        assert hot.execute("SELECT COUNT(*) FROM settlements").fetchone()[0] == 2
        assert hot.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1
        assert hot.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        hot.close()

    archive = sqlite3.connect(default_archive_path(db))
    try:
        assert archive.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 2
        assert archive.execute("SELECT COUNT(*) FROM archive_batches").fetchone()[0] == 2
        assert archive.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        archive.close()

    ledger = AutonomyLedger(db)
    try:
        assert len(ledger.signals_for_market("OLD")) == 2
        assert ledger._conn.execute("SELECT COUNT(*) FROM signal_history").fetchone()[0] == 4  # noqa: SLF001
        assert load_settled_rows(ledger._conn) == settled_before  # noqa: SLF001
        duplicate = _signal("OLD", "model_a", "2026-07-01T10:00:00+00:00")
        assert ledger.record_signal(duplicate) is False
    finally:
        ledger.close()

    dry_run = enforce_retention(db, retention_days=7, now=NOW)
    assert dry_run.history_rows_after == 4


def test_retention_rolls_back_when_archive_id_has_different_evidence(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _fixture_ledger(db)
    archive_path = default_archive_path(db)
    archive_path.parent.mkdir(parents=True)
    archive = sqlite3.connect(archive_path)
    try:
        archive.execute(
            "CREATE TABLE signals(id INTEGER PRIMARY KEY,source TEXT NOT NULL,market_ticker TEXT NOT NULL,"
            "probability_yes REAL NOT NULL,uncertainty REAL NOT NULL,rationale TEXT NOT NULL,"
            "created_at TEXT NOT NULL,mode TEXT NOT NULL,features TEXT NOT NULL,"
            "ingested_at TEXT NOT NULL,ingest_version INTEGER NOT NULL)"
        )
        archive.execute(
            "INSERT INTO signals VALUES (1,'tampered','OLD',0.1,0.1,'bad',"
            "'2026-07-01T10:00:00+00:00','live','{}','2026-07-01T10:00:00+00:00',2)"
        )
        archive.commit()
    finally:
        archive.close()

    with pytest.raises(RuntimeError, match="verification failed"):
        enforce_retention(db, retention_days=7, apply=True, now=NOW)

    source = sqlite3.connect(db)
    try:
        assert source.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 4
    finally:
        source.close()


def test_retention_applies_under_wal_source(tmp_path: Path) -> None:
    """Wave-83: the two-phase protocol makes apply safe on a WAL main ledger."""
    db = tmp_path / "ledger.db"
    _fixture_ledger(db)
    connection = sqlite3.connect(db)
    try:
        # AutonomyLedger already flips the file to WAL; pin the precondition.
        assert str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
    finally:
        connection.close()


def test_retention_retries_begin_immediate_under_writer_contention(tmp_path: Path) -> None:
    """The production failure was at BEGIN IMMEDIATE, not commit."""
    db = tmp_path / "ledger.db"
    _fixture_ledger(db)
    locked = threading.Event()

    def hold_writer() -> None:
        connection = sqlite3.connect(db, timeout=1)
        try:
            connection.execute("BEGIN IMMEDIATE")
            locked.set()
            time.sleep(0.2)
            connection.commit()
        finally:
            connection.close()

    holder = threading.Thread(target=hold_writer)
    holder.start()
    assert locked.wait(1)
    report = enforce_retention(
        db,
        retention_days=7,
        apply=True,
        now=NOW,
        sqlite_timeout_s=0.01,
        sqlite_lock_budget_s=2,
    )
    holder.join(timeout=2)
    assert not holder.is_alive()
    assert report.status == "APPLIED"
    assert report.lock_retries > 0
    assert report.archived_rows == 2


def test_retention_lock_budget_exhaustion_is_truthful(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _fixture_ledger(db)
    holder = sqlite3.connect(db, timeout=1)
    try:
        holder.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            enforce_retention(
                db,
                retention_days=7,
                apply=True,
                now=NOW,
                sqlite_timeout_s=0.01,
                sqlite_lock_budget_s=0.05,
            )
    finally:
        holder.rollback()
        holder.close()

    report = enforce_retention(db, retention_days=7, apply=True, now=NOW)

    assert report.status == "APPLIED"
    assert report.archived_rows == 2
    assert report.history_rows_after == 4
    source = sqlite3.connect(db)
    try:
        assert source.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 2
        assert source.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        source.close()


def test_retention_replays_cleanly_after_crash_between_phases(tmp_path: Path) -> None:
    """A crash after the archive commit but before the hot delete (the two-phase
    window) must be repaired by the next run: OR IGNOREs replay as no-ops, the
    delete completes, and the archive holds no duplicates."""
    db = tmp_path / "ledger.db"
    _fixture_ledger(db)
    archive_path = default_archive_path(db)
    archive_path.parent.mkdir(parents=True)

    # Simulate phase A having committed: copy the two eligible rows verbatim.
    connection = sqlite3.connect(db)
    try:
        connection.execute("ATTACH DATABASE ? AS pre", (str(archive_path),))
        connection.execute(
            "CREATE TABLE pre.signals(id INTEGER PRIMARY KEY,source TEXT NOT NULL,"
            "market_ticker TEXT NOT NULL,probability_yes REAL NOT NULL,uncertainty REAL NOT NULL,"
            "rationale TEXT NOT NULL,created_at TEXT NOT NULL,mode TEXT NOT NULL,"
            "features TEXT NOT NULL,ingested_at TEXT NOT NULL,ingest_version INTEGER NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE pre.archive_batches(batch_id TEXT PRIMARY KEY,"
            "source_database TEXT NOT NULL,cutoff_settled_at TEXT NOT NULL,"
            "first_signal_id INTEGER NOT NULL,last_signal_id INTEGER NOT NULL,"
            "row_count INTEGER NOT NULL,sha256 TEXT NOT NULL,archived_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO pre.signals SELECT id,source,market_ticker,probability_yes,"
            "uncertainty,rationale,created_at,mode,features,ingested_at,ingest_version "
            "FROM main.signals WHERE market_ticker='OLD'"
        )
        connection.commit()
    finally:
        connection.close()

    report = enforce_retention(db, retention_days=7, apply=True, now=NOW)

    assert report.status == "APPLIED"
    assert report.archived_rows == 2  # the replayed batch completes the move
    source = sqlite3.connect(db)
    try:
        assert source.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 2
    finally:
        source.close()
    archive = sqlite3.connect(archive_path)
    try:
        assert archive.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 2  # no dupes
        assert archive.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        archive.close()


def test_ensure_signal_history_installs_on_a_fresh_connection(tmp_path: Path) -> None:
    """A fresh connection has no ``signal_history``: it is a per-CONNECTION temp
    view. Two report writers queried it without installing and died with "no
    such table" for days (2026-07-24)."""
    db = tmp_path / "ledger.db"
    _fixture_ledger(db)
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError, match="signal_history"):
            conn.execute("SELECT 1 FROM signal_history LIMIT 1")
        assert ensure_signal_history(conn) is True
        assert conn.execute("SELECT COUNT(*) FROM signal_history").fetchone()[0] == 4
        # Idempotent: a second call is a no-op, not a re-install.
        assert ensure_signal_history(conn) is False
    finally:
        conn.close()


def test_ensure_signal_history_never_clobbers_a_supplied_relation() -> None:
    """Some callers pass a synthetic connection that already provides its own
    ``signal_history`` and has no ``main.signals`` to build a view over."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE signal_history(source TEXT, market_ticker TEXT)")
        conn.execute("INSERT INTO signal_history VALUES ('llm_panel_v3_x', 'T1')")
        assert ensure_signal_history(conn) is False
        assert conn.execute("SELECT source FROM signal_history").fetchone()[0] == (
            "llm_panel_v3_x"
        )
    finally:
        conn.close()


def test_report_writer_entry_points_work_on_a_fresh_connection(tmp_path: Path) -> None:
    """The exact regression: these entry points are reached before anything
    else installs the view, so each must ensure it itself."""
    from autonomy.picks import llm_voice_sources

    db = tmp_path / "ledger.db"
    _fixture_ledger(db)
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        assert llm_voice_sources(conn, days=None) == ()
    finally:
        conn.close()


def test_bounded_statements_interrupts_and_always_clears(tmp_path: Path) -> None:
    """A report writer must fail fast and recorded, not run the readiness task
    into its scheduler kill (a killed process writes no failure artifact)."""
    import time as _time

    from autonomy.retention import bounded_statements

    db = tmp_path / "ledger.db"
    _fixture_ledger(db)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "WITH RECURSIVE seed(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM seed"
            " LIMIT 20000) INSERT INTO signals(source,market_ticker,probability_yes,"
            "uncertainty,rationale,features,created_at,mode,ingested_at,ingest_version)"
            " SELECT 'perf','T'||x,0.5,0.1,'r','{}','2026-07-01T00:00:00+00:00',"
            "'live','2026-07-01T00:00:00+00:00',2 FROM seed"
        )
        conn.commit()
        with pytest.raises(sqlite3.OperationalError, match="interrupt"):
            with bounded_statements(conn, 0.05):
                _time.sleep(0.06)
                conn.execute(
                    "SELECT COUNT(*) FROM signals a, signals b"
                    " WHERE a.rationale = b.rationale"
                ).fetchone()
        # The handler is cleared even though the block raised, so the next
        # writer on this connection is not silently pre-aborted.
        assert conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 20004
        with bounded_statements(conn, 0):   # non-positive disables the bound
            assert conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 20004
    finally:
        conn.close()
