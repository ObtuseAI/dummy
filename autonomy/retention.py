"""Verified cold storage for immutable settled-market signal evidence.

The operational ledger is intentionally append-only while markets are open.
Once a market has been settled longer than the retention window, its signal
rows may be moved into a companion SQLite archive.  Readers use the temporary
``signal_history`` view, which unions hot and archived rows without changing
the evidence available to research, calibration, or governance code.

Archival is fail-closed: dry-run is the default, only signal rows are eligible,
and an apply batch is deleted from the hot ledger only after an exact row count
and SHA-256 digest match in the archive inside the same SQLite transaction.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

# Wave-81: 7 -> 5 days. The hot signals table drove the ledger's write-lock
# contention (a smaller table = faster inserts = shorter lock holds). Safe: the
# ``signal_history`` view unions hot + archived rows and every consumer reads the
# view, while the archive DB keeps rows permanently -- trimming the hot window
# only moves rows to the archive sooner, it never loses history.
DEFAULT_RETENTION_DAYS = 5.0
DEFAULT_BATCH_SIZE = 100_000
ARCHIVE_NAME = "signals_archive.db"
ARCHIVE_ALIAS = "signal_archive"

_SIGNAL_COLUMNS = (
    "id", "source", "market_ticker", "probability_yes", "uncertainty",
    "rationale", "created_at", "mode", "features", "ingested_at", "ingest_version",
)
_COLUMN_SQL = ",".join(_SIGNAL_COLUMNS)

@dataclass(frozen=True)
class RetentionReport:
    status: str
    apply: bool
    source_database: str
    archive_database: str
    retention_days: float
    cutoff_settled_at: str
    eligible_rows: int
    eligible_markets: int
    archived_rows: int
    batches: int
    source_rows_before: int
    source_rows_after: int
    history_rows_after: int
    source_bytes_before: int
    source_bytes_after: int
    archive_bytes_after: int
    vacuumed: bool
    execution_authority: bool = False
    tables_mutated: tuple[str, ...] = ("signals",)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_archive_path(db_path: Path | str) -> Path:
    source = Path(db_path)
    return source.parent / "archive" / ARCHIVE_NAME


def _database_path(connection: sqlite3.Connection, name: str = "main") -> Path | None:
    for _, database_name, filename in connection.execute("PRAGMA database_list"):
        if str(database_name) == name and filename:
            return Path(str(filename))
    return None


def install_signal_history(
    connection: sqlite3.Connection,
    archive_path: Path | str | None = None,
) -> bool:
    """Install a connection-local union view; return whether an archive was attached.

    The archive is attached read-only.  A missing archive is normal and yields
    a view over ``main.signals`` alone.  Invalid or unreadable archives raise so
    research cannot silently report a truncated history.
    """
    attached = {str(row[1]) for row in connection.execute("PRAGMA database_list")}
    source = _database_path(connection)
    archive = Path(archive_path) if archive_path is not None else (
        default_archive_path(source) if source is not None else None
    )
    has_archive = ARCHIVE_ALIAS in attached
    if archive is not None and archive.exists() and not has_archive:
        uri = f"file:{archive.resolve().as_posix()}?mode=ro"
        connection.execute(f"ATTACH DATABASE ? AS {ARCHIVE_ALIAS}", (uri,))
        has_archive = True
    connection.execute("DROP VIEW IF EXISTS temp.signal_history")
    hot = f"SELECT {_COLUMN_SQL} FROM main.signals"
    if has_archive:
        columns = tuple(
            str(row[1])
            for row in connection.execute(f"PRAGMA {ARCHIVE_ALIAS}.table_info(signals)")
        )
        if columns != _SIGNAL_COLUMNS:
            raise RuntimeError(f"archive signals schema mismatch: {columns!r}")
        archived = f"SELECT {_COLUMN_SQL} FROM {ARCHIVE_ALIAS}.signals"
        connection.execute(f"CREATE TEMP VIEW signal_history AS {hot} UNION ALL {archived}")
    else:
        connection.execute(f"CREATE TEMP VIEW signal_history AS {hot}")
    return has_archive


def _digest_rows(rows: Iterable[tuple[Any, ...]]) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for row in rows:
        payload = json.dumps(row, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        digest.update(payload.encode("utf-8"))
        digest.update(b"\n")
        count += 1
    return count, digest.hexdigest()


def _candidate_digest(connection: sqlite3.Connection, database: str) -> tuple[int, str]:
    rows = connection.execute(
        f"SELECT {','.join(f's.{column}' for column in _SIGNAL_COLUMNS)} "
        f"FROM {database}.signals s JOIN temp.archive_candidates c ON c.id=s.id ORDER BY s.id"
    )
    return _digest_rows(rows)


def _eligible_summary(connection: sqlite3.Connection, cutoff: str) -> tuple[int, int]:
    row = connection.execute(
        "SELECT COUNT(*),COUNT(DISTINCT s.market_ticker) FROM main.signals s "
        "JOIN main.settlements st ON st.market_ticker=s.market_ticker "
        "WHERE julianday(st.settled_at)<=julianday(?)",
        (cutoff,),
    ).fetchone()
    return int(row[0] or 0), int(row[1] or 0)


def _existing_archive_rows(archive: Path) -> int:
    if not archive.exists():
        return 0
    connection = sqlite3.connect(
        f"file:{archive.as_posix()}?mode=ro", uri=True,
    )
    try:
        columns = tuple(str(row[1]) for row in connection.execute("PRAGMA table_info(signals)"))
        if columns != _SIGNAL_COLUMNS:
            raise RuntimeError(f"archive signals schema mismatch: {columns!r}")
        return int(connection.execute("SELECT COUNT(*) FROM signals").fetchone()[0])
    finally:
        connection.close()


def _ensure_archive_schema(connection: sqlite3.Connection) -> None:
    # executescript cannot safely qualify every statement via a string replace;
    # create the two tables explicitly in the attached database instead.
    connection.execute(
        f"CREATE TABLE IF NOT EXISTS {ARCHIVE_ALIAS}.signals ("
        "id INTEGER PRIMARY KEY,source TEXT NOT NULL,market_ticker TEXT NOT NULL,"
        "probability_yes REAL NOT NULL,uncertainty REAL NOT NULL,rationale TEXT NOT NULL,"
        "created_at TEXT NOT NULL,mode TEXT NOT NULL,features TEXT NOT NULL,"
        "ingested_at TEXT NOT NULL,ingest_version INTEGER NOT NULL)"
    )
    connection.execute(
        f"CREATE TABLE IF NOT EXISTS {ARCHIVE_ALIAS}.archive_batches ("
        "batch_id TEXT PRIMARY KEY,source_database TEXT NOT NULL,"
        "cutoff_settled_at TEXT NOT NULL,first_signal_id INTEGER NOT NULL,"
        "last_signal_id INTEGER NOT NULL,row_count INTEGER NOT NULL,sha256 TEXT NOT NULL,"
        "archived_at TEXT NOT NULL)"
    )
    columns = tuple(
        str(row[1]) for row in connection.execute(f"PRAGMA {ARCHIVE_ALIAS}.table_info(signals)")
    )
    if columns != _SIGNAL_COLUMNS:
        raise RuntimeError(f"archive signals schema mismatch: {columns!r}")


def enforce_retention(
    db_path: Path | str,
    *,
    archive_path: Path | str | None = None,
    retention_days: float = DEFAULT_RETENTION_DAYS,
    apply: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    vacuum: bool = False,
    now: datetime | None = None,
) -> RetentionReport:
    """Archive eligible rows, or report what would be archived.

    ``apply=False`` never creates an archive or mutates the source.  Apply mode
    refuses WAL because SQLite cannot guarantee atomic multi-database commits
    when the main database is WAL-backed.
    """
    source = Path(db_path).resolve()
    archive = Path(archive_path).resolve() if archive_path else default_archive_path(source).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if source == archive:
        raise ValueError("archive database must differ from source database")
    if retention_days < 1.0:
        raise ValueError("retention_days must be at least 1")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    clock = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = (clock - timedelta(days=retention_days)).isoformat()
    source_bytes_before = source.stat().st_size

    connection = sqlite3.connect(
        f"file:{source.as_posix()}?mode=rw", uri=True, timeout=60.0,
    )
    try:
        source_rows_before = int(connection.execute("SELECT COUNT(*) FROM main.signals").fetchone()[0])
        eligible_rows, eligible_markets = _eligible_summary(connection, cutoff)
        if not apply:
            archive_rows = _existing_archive_rows(archive)
            return RetentionReport(
                status="DRY_RUN", apply=False, source_database=str(source),
                archive_database=str(archive), retention_days=retention_days,
                cutoff_settled_at=cutoff, eligible_rows=eligible_rows,
                eligible_markets=eligible_markets, archived_rows=0, batches=0,
                source_rows_before=source_rows_before, source_rows_after=source_rows_before,
                history_rows_after=source_rows_before + archive_rows,
                source_bytes_before=source_bytes_before,
                source_bytes_after=source_bytes_before,
                archive_bytes_after=archive.stat().st_size if archive.exists() else 0,
                vacuumed=False,
            )

        journal_mode = str(connection.execute("PRAGMA main.journal_mode").fetchone()[0]).lower()
        if journal_mode == "wal":
            raise RuntimeError("apply refused: main ledger uses WAL; atomic archive+delete is not guaranteed")
        archive.parent.mkdir(parents=True, exist_ok=True)
        uri = f"file:{archive.as_posix()}?mode=rwc"
        connection.execute(f"ATTACH DATABASE ? AS {ARCHIVE_ALIAS}", (uri,))
        archive_journal_mode = str(
            connection.execute(f"PRAGMA {ARCHIVE_ALIAS}.journal_mode").fetchone()[0]
        ).lower()
        if archive_journal_mode == "wal":
            raise RuntimeError(
                "apply refused: signal archive uses WAL; atomic archive+delete is not guaranteed"
            )
        _ensure_archive_schema(connection)
        connection.commit()
        connection.execute("CREATE TEMP TABLE archive_candidates(id INTEGER PRIMARY KEY)")

        archived_rows = 0
        batches = 0
        while True:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute("DELETE FROM temp.archive_candidates")
                connection.execute(
                    "INSERT INTO temp.archive_candidates(id) "
                    "SELECT s.id FROM main.signals s JOIN main.settlements st "
                    "ON st.market_ticker=s.market_ticker "
                    "WHERE julianday(st.settled_at)<=julianday(?) ORDER BY s.id LIMIT ?",
                    (cutoff, batch_size),
                )
                candidate_count = int(
                    connection.execute("SELECT COUNT(*) FROM temp.archive_candidates").fetchone()[0]
                )
                if candidate_count == 0:
                    connection.rollback()
                    break
                first_id, last_id = connection.execute(
                    "SELECT MIN(id),MAX(id) FROM temp.archive_candidates"
                ).fetchone()
                source_count, source_digest = _candidate_digest(connection, "main")
                connection.execute(
                    f"INSERT OR IGNORE INTO {ARCHIVE_ALIAS}.signals({_COLUMN_SQL}) "
                    f"SELECT {','.join(f's.{column}' for column in _SIGNAL_COLUMNS)} "
                    "FROM main.signals s JOIN temp.archive_candidates c ON c.id=s.id"
                )
                archive_count, archive_digest = _candidate_digest(connection, ARCHIVE_ALIAS)
                if (
                    source_count != candidate_count
                    or archive_count != candidate_count
                    or source_digest != archive_digest
                ):
                    raise RuntimeError("archive verification failed; source deletion rolled back")
                deleted = connection.execute(
                    "DELETE FROM main.signals WHERE id IN (SELECT id FROM temp.archive_candidates)"
                ).rowcount
                if deleted != candidate_count:
                    raise RuntimeError("source delete count mismatch; batch rolled back")
                archived_at = datetime.now(timezone.utc).isoformat()
                batch_id = f"{int(first_id)}-{int(last_id)}-{source_digest[:16]}"
                connection.execute(
                    f"INSERT INTO {ARCHIVE_ALIAS}.archive_batches VALUES (?,?,?,?,?,?,?,?)",
                    (
                        batch_id, str(source), cutoff, int(first_id), int(last_id),
                        candidate_count, source_digest, archived_at,
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            archived_rows += candidate_count
            batches += 1

        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {ARCHIVE_ALIAS}.idx_archive_signal_identity "
            "ON signals(source,market_ticker,created_at,mode)"
        )
        connection.commit()
        source_integrity = str(connection.execute("PRAGMA main.integrity_check").fetchone()[0])
        archive_integrity = str(
            connection.execute(f"PRAGMA {ARCHIVE_ALIAS}.integrity_check").fetchone()[0]
        )
        if source_integrity != "ok" or archive_integrity != "ok":
            raise RuntimeError(
                f"post-archive integrity failure: source={source_integrity}, archive={archive_integrity}"
            )
        archive_rows = int(
            connection.execute(f"SELECT COUNT(*) FROM {ARCHIVE_ALIAS}.signals").fetchone()[0]
        )
        source_rows_after = int(connection.execute("SELECT COUNT(*) FROM main.signals").fetchone()[0])
        if vacuum and archived_rows:
            connection.execute(f"DETACH DATABASE {ARCHIVE_ALIAS}")
            connection.execute("VACUUM main")
        history_rows_after = source_rows_after + archive_rows
    finally:
        connection.close()

    return RetentionReport(
        status="APPLIED", apply=True, source_database=str(source), archive_database=str(archive),
        retention_days=retention_days, cutoff_settled_at=cutoff,
        eligible_rows=eligible_rows, eligible_markets=eligible_markets,
        archived_rows=archived_rows, batches=batches,
        source_rows_before=source_rows_before, source_rows_after=source_rows_after,
        history_rows_after=history_rows_after, source_bytes_before=source_bytes_before,
        source_bytes_after=source.stat().st_size,
        archive_bytes_after=archive.stat().st_size, vacuumed=bool(vacuum and archived_rows),
    )
