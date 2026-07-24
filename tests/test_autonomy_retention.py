from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal
from autonomy.retention import default_archive_path, enforce_retention
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
