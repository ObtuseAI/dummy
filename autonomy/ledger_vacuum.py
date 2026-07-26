"""Verified cooperative VACUUM for the operational ledger.

This deliberately never disables scheduled tasks and never kills processes.
New daemon cycles honor the shared maintenance lease; any already-running
writer is handled by SQLite with a bounded wait. A recent restore-verified
backup is mandatory before the first page is rewritten.
"""
from __future__ import annotations

import shutil
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from autonomy.ledger_backup import require_recent_verified_backup
from autonomy.maintenance import acquire_maintenance, release_maintenance, retry_sqlite_locked


@dataclass(frozen=True)
class VacuumReport:
    status: str
    database: str
    bytes_before: int
    bytes_after: int
    reclaimed_bytes: int
    freelist_bytes_before: int
    duration_seconds: float
    backup_manifest: str
    quick_check_before: tuple[str, ...]
    quick_check_after: tuple[str, ...]
    wal_checkpoint: str
    execution_authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _check(connection: sqlite3.Connection) -> tuple[str, ...]:
    return tuple(str(row[0]) for row in connection.execute("PRAGMA quick_check"))


def vacuum_ledger(
    db_path: Path | str,
    *,
    backup_manifest: Path | str,
    min_freelist_bytes: int = 1_500_000_000,
    free_space_multiplier: float = 1.25,
    backup_max_age_hours: float = 30.0,
    maintenance_wait_s: float = 300.0,
    sqlite_lock_budget_s: float = 300.0,
    max_runtime_s: float = 7200.0,
    now: datetime | None = None,
) -> VacuumReport:
    database = Path(db_path).resolve()
    manifest = Path(backup_manifest).resolve()
    if not database.is_file():
        raise FileNotFoundError(database)
    if min_freelist_bytes < 0:
        raise ValueError("min_freelist_bytes must be non-negative")
    if free_space_multiplier < 1.0:
        raise ValueError("free_space_multiplier must be at least 1")
    require_recent_verified_backup(
        manifest,
        [database],
        max_age_hours=backup_max_age_hours,
        now=now,
    )
    lease = acquire_maintenance(
        database, "ledger_vacuum", wait_seconds=maintenance_wait_s,
    )
    connection: sqlite3.Connection | None = None
    started = time.monotonic()
    try:
        before = int(database.stat().st_size)
        available = int(shutil.disk_usage(database.parent).free)
        required = int(before * free_space_multiplier)
        if available < required:
            raise RuntimeError(
                f"insufficient free space for VACUUM: required={required} "
                f"available={available}"
            )
        connection = sqlite3.connect(
            f"file:{database.as_posix()}?mode=rw",
            uri=True,
            timeout=min(5.0, max(0.1, sqlite_lock_budget_s)),
        )
        connection.execute(
            f"PRAGMA busy_timeout={int(min(5.0, max(0.1, sqlite_lock_budget_s)) * 1000)}"
        )
        quick_before = _check(connection)
        if quick_before != ("ok",):
            raise RuntimeError(f"pre-VACUUM quick_check failed: {quick_before[:5]}")
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        freelist = int(connection.execute("PRAGMA freelist_count").fetchone()[0])
        freelist_bytes = page_size * freelist
        if freelist_bytes < min_freelist_bytes:
            return VacuumReport(
                status="SKIPPED_BELOW_THRESHOLD",
                database=str(database),
                bytes_before=before,
                bytes_after=before,
                reclaimed_bytes=0,
                freelist_bytes_before=freelist_bytes,
                duration_seconds=round(time.monotonic() - started, 3),
                backup_manifest=str(manifest),
                quick_check_before=quick_before,
                quick_check_after=quick_before,
                wal_checkpoint="NOT_RUN",
            )
        busy, log_pages, checkpointed = connection.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()
        wal_status = (
            f"BUSY:{int(checkpointed)}/{int(log_pages)}"
            if int(busy) else f"OK:{int(checkpointed)}/{int(log_pages)}"
        )
        if int(busy):
            raise RuntimeError(
                "pre-VACUUM WAL checkpoint is busy; no pages were rewritten"
            )
        statement_deadline = time.monotonic() + max(1.0, float(max_runtime_s))

        def _past_deadline() -> int:
            return 1 if time.monotonic() >= statement_deadline else 0

        connection.set_progress_handler(_past_deadline, 500_000)
        try:
            retry_sqlite_locked(
                lambda: connection.execute("VACUUM"),
                deadline_monotonic=min(
                    statement_deadline,
                    time.monotonic() + max(0.1, sqlite_lock_budget_s),
                ),
            )
        finally:
            connection.set_progress_handler(None, 0)
        quick_after = _check(connection)
        if quick_after != ("ok",):
            raise RuntimeError(f"post-VACUUM quick_check failed: {quick_after[:5]}")
        after = int(database.stat().st_size)
        return VacuumReport(
            status="APPLIED",
            database=str(database),
            bytes_before=before,
            bytes_after=after,
            reclaimed_bytes=max(0, before - after),
            freelist_bytes_before=freelist_bytes,
            duration_seconds=round(time.monotonic() - started, 3),
            backup_manifest=str(manifest),
            quick_check_before=quick_before,
            quick_check_after=quick_after,
            wal_checkpoint=wal_status,
        )
    finally:
        if connection is not None:
            connection.close()
        release_maintenance(lease)
