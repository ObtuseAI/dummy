"""Durable SQLite WAL implementation of Dummy's operational journal.

The JSONL journal remains useful as a compact reference implementation.  This
module provides the production storage shape: indexed reads, an indexed
outbox, and cross-process compare-and-append semantics under
``BEGIN IMMEDIATE``.  Events retain the exact canonical event schema and hash
chain used by :mod:`live_firewall.operational_journal`.

SQLite is used as a transactional append log, not as mutable application
state.  Triggers reject event updates and deletes, and a singleton metadata row
tracks the committed sequence and hash-chain head.  A restart performs a
streaming full-chain verification; normal operations verify only the known
head and any newly committed tail.

The internal chain detects mutation, truncation against its current metadata,
and schema corruption.  Like the JSONL implementation, it cannot by itself
distinguish a byte-for-byte rollback to an older valid database snapshot.
Deployment that must resist privileged whole-file rollback needs a monotonic
head anchor outside this database (for example, a Core-signed checkpoint).
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn, cast

from live_firewall.operational_journal import (
    AppendOnlyOperationalJournal,
    OPERATIONAL_EVENT_SCHEMA,
    OperationalJournalError,
    canonical_json,
    sha256_json,
)


SQLITE_OPERATIONAL_JOURNAL_SCHEMA = "dummy.sqlite-operational-journal.v1"
_APPLICATION_ID = 0x444D4A31  # ASCII "DMJ1".
_SCHEMA_VERSION = 1
_ZERO_SHA256 = "0" * 64
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_EVENT_COLUMNS = (
    "sequence, kind, outbox_id, acknowledges_outbox_id, "
    "previous_sha256, event_sha256, event_json"
)

_CREATE_METADATA = f"""
CREATE TABLE journal_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema TEXT NOT NULL CHECK (schema = '{SQLITE_OPERATIONAL_JOURNAL_SCHEMA}'),
    event_count INTEGER NOT NULL CHECK (event_count >= 0),
    head_sha256 TEXT NOT NULL CHECK (length(head_sha256) = 64)
)
""".strip()

_CREATE_EVENTS = """
CREATE TABLE operational_events (
    sequence INTEGER PRIMARY KEY CHECK (sequence > 0),
    kind TEXT NOT NULL CHECK (length(kind) > 0),
    outbox_id TEXT UNIQUE,
    acknowledges_outbox_id TEXT UNIQUE,
    previous_sha256 TEXT NOT NULL CHECK (length(previous_sha256) = 64),
    event_sha256 TEXT NOT NULL UNIQUE CHECK (length(event_sha256) = 64),
    event_json TEXT NOT NULL
)
""".strip()

_CREATE_KIND_INDEX = """
CREATE INDEX operational_events_kind_sequence_idx
ON operational_events (kind, sequence)
""".strip()

_CREATE_OUTBOX_INDEX = """
CREATE INDEX operational_events_outbox_sequence_idx
ON operational_events (outbox_id, sequence)
WHERE outbox_id IS NOT NULL
""".strip()

_CREATE_ACK_INDEX = """
CREATE INDEX operational_events_ack_target_idx
ON operational_events (acknowledges_outbox_id)
WHERE acknowledges_outbox_id IS NOT NULL
""".strip()

_CREATE_VALIDATE_INSERT_TRIGGER = """
CREATE TRIGGER operational_events_validate_insert
BEFORE INSERT ON operational_events
BEGIN
    SELECT CASE
        WHEN NEW.sequence != (
            SELECT event_count + 1
            FROM journal_metadata
            WHERE singleton = 1
        )
        THEN RAISE(ABORT, 'journal sequence mismatch')
    END;
    SELECT CASE
        WHEN NEW.previous_sha256 != (
            SELECT head_sha256
            FROM journal_metadata
            WHERE singleton = 1
        )
        THEN RAISE(ABORT, 'journal previous hash mismatch')
    END;
END
""".strip()

_CREATE_ADVANCE_HEAD_TRIGGER = """
CREATE TRIGGER operational_events_advance_head
AFTER INSERT ON operational_events
BEGIN
    UPDATE journal_metadata
    SET event_count = NEW.sequence,
        head_sha256 = NEW.event_sha256
    WHERE singleton = 1;
END
""".strip()

_CREATE_NO_UPDATE_TRIGGER = """
CREATE TRIGGER operational_events_no_update
BEFORE UPDATE ON operational_events
BEGIN
    SELECT RAISE(ABORT, 'operational events are append-only');
END
""".strip()

_CREATE_NO_DELETE_TRIGGER = """
CREATE TRIGGER operational_events_no_delete
BEFORE DELETE ON operational_events
BEGIN
    SELECT RAISE(ABORT, 'operational events are append-only');
END
""".strip()

_SCHEMA_OBJECTS = {
    "journal_metadata": ("table", _CREATE_METADATA),
    "operational_events": ("table", _CREATE_EVENTS),
    "operational_events_kind_sequence_idx": ("index", _CREATE_KIND_INDEX),
    "operational_events_outbox_sequence_idx": ("index", _CREATE_OUTBOX_INDEX),
    "operational_events_ack_target_idx": ("index", _CREATE_ACK_INDEX),
    "operational_events_validate_insert": (
        "trigger",
        _CREATE_VALIDATE_INSERT_TRIGGER,
    ),
    "operational_events_advance_head": (
        "trigger",
        _CREATE_ADVANCE_HEAD_TRIGGER,
    ),
    "operational_events_no_update": ("trigger", _CREATE_NO_UPDATE_TRIGGER),
    "operational_events_no_delete": ("trigger", _CREATE_NO_DELETE_TRIGGER),
}


def _normalized_sql(value: str) -> str:
    return " ".join(value.split()).casefold()


def _validated_page(
    *,
    after_sequence: int,
    limit: int | None,
) -> tuple[int, int | None]:
    if isinstance(after_sequence, bool) or not isinstance(after_sequence, int):
        raise TypeError("after_sequence must be an integer")
    if after_sequence < 0:
        raise ValueError("after_sequence cannot be negative")
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit must be an integer")
        if limit <= 0:
            raise ValueError("limit must be positive")
        if limit > 9_223_372_036_854_775_807:
            raise ValueError("limit exceeds SQLite integer range")
    return after_sequence, limit


class SQLiteOperationalJournal(AppendOnlyOperationalJournal):
    """Hash-chained operational journal backed by durable SQLite WAL.

    ``events`` and ``pending_outbox`` accept optional ``after_sequence`` and
    ``limit`` arguments for bounded incremental consumers.  Omitting them
    preserves the return behavior of :class:`AppendOnlyOperationalJournal`.
    The legacy ``validate_existing`` callback receives a real tuple for API
    compatibility and therefore materializes history; high-volume consumers
    should use indexed pages and a purpose-built transactional projection.
    """

    def __init__(
        self,
        path: Path,
        *,
        now_fn: Callable[[], datetime] | None = None,
        busy_timeout_seconds: float = 5.0,
        scan_batch_size: int = 256,
        wal_autocheckpoint_pages: int = 256,
        journal_size_limit_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        self.path = Path(path)
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        if (
            isinstance(busy_timeout_seconds, bool)
            or not isinstance(busy_timeout_seconds, (int, float))
            or not 0 < float(busy_timeout_seconds) <= 60
        ):
            raise ValueError("busy_timeout_seconds must be in (0, 60]")
        if (
            isinstance(scan_batch_size, bool)
            or not isinstance(scan_batch_size, int)
            or not 1 <= scan_batch_size <= 10_000
        ):
            raise ValueError("scan_batch_size must be in [1, 10000]")
        if (
            isinstance(wal_autocheckpoint_pages, bool)
            or not isinstance(wal_autocheckpoint_pages, int)
            or not 1 <= wal_autocheckpoint_pages <= 100_000
        ):
            raise ValueError("wal_autocheckpoint_pages must be in [1, 100000]")
        if (
            isinstance(journal_size_limit_bytes, bool)
            or not isinstance(journal_size_limit_bytes, int)
            or journal_size_limit_bytes < 1_048_576
        ):
            raise ValueError("journal_size_limit_bytes must be at least 1 MiB")

        self._busy_timeout_seconds = float(busy_timeout_seconds)
        self._scan_batch_size = scan_batch_size
        self._wal_autocheckpoint_pages = wal_autocheckpoint_pages
        self._journal_size_limit_bytes = journal_size_limit_bytes
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None
        self._error: str | None = None
        self._closed = False
        self._operation_depth = 0
        self._verified_sequence = 0
        self._verified_head = _ZERO_SHA256
        self._observed_data_version: int | None = None
        self._observed_schema_version: int | None = None

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(
                str(self.path),
                timeout=self._busy_timeout_seconds,
                isolation_level=None,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            self._configure_connection(self._connection)
            self._initialize_or_validate_schema(self._connection)
            self._connection.execute("BEGIN")
            try:
                self._verify_full_chain_locked(self._connection)
                (
                    self._observed_data_version,
                    self._observed_schema_version,
                ) = self._database_versions(self._connection)
                self._connection.execute("COMMIT")
            except BaseException:
                self._rollback_quietly(self._connection)
                raise
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"

    @property
    def healthy(self) -> bool:
        with self._lock:
            if self._error is not None or self._closed:
                return False
            try:
                with self._transaction(write=False) as connection:
                    self._synchronize_integrity_locked(connection)
            except Exception as exc:
                if self._error is None:
                    self._error = f"{type(exc).__name__}: {exc}"
                return False
            return True

    @property
    def error(self) -> str | None:
        # Probe first so a metadata/head mutation is surfaced without requiring
        # a separate read or append call.
        _ = self.healthy
        with self._lock:
            if self._closed and self._error is None:
                return "OperationalJournalError: operational journal is closed"
            return self._error

    def close(self) -> None:
        """Close this process-local connection.

        A journal must not be closed from inside ``serialized_operation``.
        """
        with self._lock:
            if self._closed:
                return
            if self._operation_depth:
                raise OperationalJournalError(
                    "cannot close journal during serialized operation"
                )
            connection = self._connection
            self._connection = None
            self._closed = True
            if connection is not None:
                connection.close()

    def __enter__(self) -> SQLiteOperationalJournal:
        if not self.healthy:
            raise OperationalJournalError(
                f"operational journal unhealthy: {self.error}"
            )
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()

    def events(
        self,
        *,
        kind: str | None = None,
        after_sequence: int = 0,
        limit: int | None = None,
    ) -> tuple[dict[str, Any], ...]:
        """Return immutable event copies, optionally as a bounded page."""
        normalized_after, normalized_limit = _validated_page(
            after_sequence=after_sequence,
            limit=limit,
        )
        if kind is not None and not isinstance(kind, str):
            raise TypeError("kind must be a string or None")

        with self._lock:
            self._raise_if_unavailable()
            try:
                with self._transaction(write=False) as connection:
                    self._synchronize_integrity_locked(connection)
                    clauses = ["sequence > ?"]
                    parameters: list[Any] = [normalized_after]
                    if kind is not None:
                        clauses.append("kind = ?")
                        parameters.append(kind)
                    sql = (
                        f"SELECT {_EVENT_COLUMNS} FROM operational_events "
                        f"WHERE {' AND '.join(clauses)} ORDER BY sequence"
                    )
                    if normalized_limit is not None:
                        sql += " LIMIT ?"
                        parameters.append(normalized_limit)
                    rows = connection.execute(sql, parameters).fetchall()
                    return tuple(self._copy_row(row) for row in rows)
            except sqlite3.Error as exc:
                self._poison_sqlite("operational journal read failed", exc)

    def head(self) -> tuple[int, str]:
        """Return the integrity-verified committed sequence and chain head."""
        with self._lock:
            self._raise_if_unavailable()
            try:
                with self._transaction(write=False) as connection:
                    self._synchronize_integrity_locked(connection)
                    return self._verified_sequence, self._verified_head
            except sqlite3.Error as exc:
                self._poison_sqlite(
                    "operational journal head read failed",
                    exc,
                )

    @contextmanager
    def serialized_operation(self) -> Iterator[None]:
        """Hold one cross-process writer transaction across caller operations."""
        with self._lock:
            self._raise_if_unavailable()
            if self._operation_depth:
                self._operation_depth += 1
                try:
                    yield
                finally:
                    self._operation_depth -= 1
                return

            connection = self._require_connection()
            old_verified = self._verification_state()
            begun = False
            try:
                connection.execute("BEGIN IMMEDIATE")
                begun = True
                self._synchronize_integrity_locked(connection)
                self._operation_depth = 1
                try:
                    yield
                finally:
                    self._operation_depth = 0
                connection.execute("COMMIT")
            except sqlite3.Error as exc:
                if begun:
                    self._rollback_quietly(connection)
                self._restore_verification_state(old_verified)
                self._poison_sqlite(
                    "operational journal serialized operation failed",
                    exc,
                )
            except BaseException:
                if begun:
                    self._rollback_quietly(connection)
                self._restore_verification_state(old_verified)
                raise

    def append(
        self,
        kind: str,
        payload: Mapping[str, Any],
        *,
        outbox_id: str | None = None,
        allow_existing_outbox: bool = True,
        validate_existing: (
            Callable[[tuple[dict[str, Any], ...]], None] | None
        ) = None,
        validate_existing_latest_kinds: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        """Atomically validate current history and append one durable event.

        ``validate_existing_latest_kinds`` is an opt-in bounded validation
        view.  When supplied, ``validate_existing`` receives at most the latest
        event for each named kind, in sequence order.  This supports atomic
        compare-and-swap on high-frequency state streams without repeatedly
        materializing the full journal.  Omitting it preserves the reference
        journal's full-history callback contract.
        """
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("journal kind is required")
        normalized_validation_kinds = self._validated_latest_kinds(
            validate_existing=validate_existing,
            kinds=validate_existing_latest_kinds,
        )
        normalized_payload = cast(
            dict[str, Any],
            json.loads(canonical_json(dict(payload))),
        )
        normalized_outbox = (
            str(outbox_id).strip() if outbox_id is not None else None
        )
        if normalized_outbox == "":
            raise ValueError("outbox_id cannot be blank")

        with self._lock:
            self._raise_if_unavailable()
            try:
                with self._transaction(write=True) as connection:
                    self._synchronize_integrity_locked(connection)
                    return self._append_locked(
                        connection,
                        kind=kind,
                        payload=normalized_payload,
                        outbox_id=normalized_outbox,
                        allow_existing_outbox=allow_existing_outbox,
                        validate_existing=validate_existing,
                        validate_existing_latest_kinds=(
                            normalized_validation_kinds
                        ),
                    )
            except sqlite3.Error as exc:
                self._poison_sqlite("operational journal append failed", exc)

    def acknowledge_outbox(
        self,
        outbox_id: str,
        *,
        acknowledgement: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = str(outbox_id).strip()
        with self._lock:
            self._raise_if_unavailable()
            try:
                with self._transaction(write=True) as connection:
                    self._synchronize_integrity_locked(connection)
                    source_row = connection.execute(
                        f"SELECT {_EVENT_COLUMNS} FROM operational_events "
                        "WHERE outbox_id = ?",
                        (normalized,),
                    ).fetchone()
                    if source_row is None:
                        raise OperationalJournalError(
                            "cannot acknowledge unknown outbox id"
                        )
                    source = self._copy_row(source_row)
                    payload = cast(
                        dict[str, Any],
                        json.loads(
                            canonical_json(
                                {
                                    "outbox_id": normalized,
                                    "source_event_sha256": source[
                                        "event_sha256"
                                    ],
                                    "acknowledgement": dict(
                                        acknowledgement or {}
                                    ),
                                }
                            )
                        ),
                    )
                    return self._append_locked(
                        connection,
                        kind="outbox.acknowledged",
                        payload=payload,
                        outbox_id=f"ack:{normalized}",
                        allow_existing_outbox=True,
                        validate_existing=None,
                        validate_existing_latest_kinds=None,
                    )
            except sqlite3.Error as exc:
                self._poison_sqlite(
                    "operational journal acknowledgement failed",
                    exc,
                )

    def pending_outbox(
        self,
        *,
        after_sequence: int = 0,
        limit: int | None = None,
    ) -> tuple[dict[str, Any], ...]:
        """Return unacknowledged outbox events as an indexed bounded page."""
        normalized_after, normalized_limit = _validated_page(
            after_sequence=after_sequence,
            limit=limit,
        )
        with self._lock:
            self._raise_if_unavailable()
            try:
                with self._transaction(write=False) as connection:
                    self._synchronize_integrity_locked(connection)
                    sql = (
                        f"SELECT {_EVENT_COLUMNS} "
                        "FROM operational_events AS source "
                        "WHERE source.sequence > ? "
                        "AND source.outbox_id IS NOT NULL "
                        "AND source.kind != 'outbox.acknowledged' "
                        "AND NOT EXISTS ("
                        "    SELECT 1 FROM operational_events AS acknowledgement "
                        "    WHERE acknowledgement.acknowledges_outbox_id = "
                        "          source.outbox_id"
                        ") "
                        "ORDER BY source.sequence"
                    )
                    parameters: list[Any] = [normalized_after]
                    if normalized_limit is not None:
                        sql += " LIMIT ?"
                        parameters.append(normalized_limit)
                    rows = connection.execute(sql, parameters).fetchall()
                    return tuple(self._copy_row(row) for row in rows)
            except sqlite3.Error as exc:
                self._poison_sqlite(
                    "operational journal outbox read failed",
                    exc,
                )

    @contextmanager
    def _transaction(
        self,
        *,
        write: bool,
    ) -> Iterator[sqlite3.Connection]:
        connection = self._require_connection()
        if self._operation_depth:
            yield connection
            return

        old_verified = self._verification_state()
        begun = False
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            begun = True
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if begun:
                self._rollback_quietly(connection)
            self._restore_verification_state(old_verified)
            raise

    def _append_locked(
        self,
        connection: sqlite3.Connection,
        *,
        kind: str,
        payload: dict[str, Any],
        outbox_id: str | None,
        allow_existing_outbox: bool,
        validate_existing: (
            Callable[[tuple[dict[str, Any], ...]], None] | None
        ),
        validate_existing_latest_kinds: tuple[str, ...] | None,
    ) -> dict[str, Any]:
        if outbox_id is not None:
            existing_row = connection.execute(
                f"SELECT {_EVENT_COLUMNS} FROM operational_events "
                "WHERE outbox_id = ?",
                (outbox_id,),
            ).fetchone()
            if existing_row is not None:
                existing = self._copy_row(existing_row)
                if not allow_existing_outbox:
                    raise OperationalJournalError(
                        "outbox id is already claimed"
                    )
                if (
                    existing.get("kind") == kind
                    and existing.get("payload") == payload
                ):
                    return existing
                raise OperationalJournalError(
                    "outbox id reused with different content"
                )

        if validate_existing is not None:
            if validate_existing_latest_kinds is None:
                validation_rows = self._all_events_locked(connection)
            else:
                validation_rows = self._latest_kinds_locked(
                    connection,
                    validate_existing_latest_kinds,
                )
            validate_existing(validation_rows)

        now = self._now_fn()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("journal clock must be timezone-aware")
        sequence = self._verified_sequence + 1
        event: dict[str, Any] = {
            "schema": OPERATIONAL_EVENT_SCHEMA,
            "sequence": sequence,
            "recorded_at": now.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "kind": kind,
            "payload": payload,
            "previous_sha256": self._verified_head,
        }
        if outbox_id is not None:
            event["outbox_id"] = outbox_id
        event["event_sha256"] = sha256_json(event)
        event_json = canonical_json(event)
        acknowledgement_target = self._acknowledgement_target(event)

        connection.execute(
            """
            INSERT INTO operational_events (
                sequence,
                kind,
                outbox_id,
                acknowledges_outbox_id,
                previous_sha256,
                event_sha256,
                event_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sequence,
                kind,
                outbox_id,
                acknowledgement_target,
                self._verified_head,
                event["event_sha256"],
                event_json,
            ),
        )
        metadata = self._metadata_locked(connection)
        if (
            metadata[0] != sequence
            or metadata[1] != event["event_sha256"]
        ):
            self._integrity_failure("journal head trigger did not advance")
        self._verified_sequence = sequence
        self._verified_head = str(event["event_sha256"])
        return cast(dict[str, Any], json.loads(event_json))

    def _all_events_locked(
        self,
        connection: sqlite3.Connection,
    ) -> tuple[dict[str, Any], ...]:
        cursor = connection.execute(
            f"SELECT {_EVENT_COLUMNS} FROM operational_events "
            "ORDER BY sequence"
        )
        events: list[dict[str, Any]] = []
        while True:
            rows = cursor.fetchmany(self._scan_batch_size)
            if not rows:
                break
            events.extend(self._copy_row(row) for row in rows)
        return tuple(events)

    def _latest_kinds_locked(
        self,
        connection: sqlite3.Connection,
        kinds: tuple[str, ...],
    ) -> tuple[dict[str, Any], ...]:
        rows: list[dict[str, Any]] = []
        for kind in kinds:
            row = connection.execute(
                f"SELECT {_EVENT_COLUMNS} FROM operational_events "
                "WHERE kind = ? ORDER BY sequence DESC LIMIT 1",
                (kind,),
            ).fetchone()
            if row is not None:
                rows.append(self._copy_row(row))
        rows.sort(key=lambda event: int(event["sequence"]))
        return tuple(rows)

    @staticmethod
    def _validated_latest_kinds(
        *,
        validate_existing: (
            Callable[[tuple[dict[str, Any], ...]], None] | None
        ),
        kinds: tuple[str, ...] | None,
    ) -> tuple[str, ...] | None:
        if kinds is None:
            return None
        if validate_existing is None:
            raise ValueError(
                "validate_existing_latest_kinds requires validate_existing"
            )
        if not isinstance(kinds, tuple):
            raise TypeError(
                "validate_existing_latest_kinds must be a tuple"
            )
        if not 1 <= len(kinds) <= 64:
            raise ValueError(
                "validate_existing_latest_kinds must contain 1 to 64 kinds"
            )
        normalized: list[str] = []
        for kind in kinds:
            if not isinstance(kind, str) or not kind.strip():
                raise ValueError("validation kind must be a non-blank string")
            if kind not in normalized:
                normalized.append(kind)
        return tuple(normalized)

    def _copy_row(self, row: sqlite3.Row) -> dict[str, Any]:
        event = self._decode_row(row)
        return cast(dict[str, Any], json.loads(canonical_json(event)))

    def _decode_row(
        self,
        row: sqlite3.Row,
        *,
        expected_sequence: int | None = None,
        expected_previous: str | None = None,
    ) -> dict[str, Any]:
        event_json = row["event_json"]
        if not isinstance(event_json, str):
            self._integrity_failure("journal event JSON is not text")
        try:
            value = json.loads(event_json)
        except (TypeError, ValueError) as exc:
            self._integrity_failure(
                f"journal event JSON is invalid: {type(exc).__name__}"
            )
        if not isinstance(value, dict):
            self._integrity_failure("journal event must be an object")
        event = cast(dict[str, Any], value)
        try:
            is_canonical = canonical_json(event) == event_json
        except (TypeError, ValueError) as exc:
            self._integrity_failure(
                f"journal event cannot be canonicalized: {type(exc).__name__}"
            )
        if not is_canonical:
            self._integrity_failure("journal event is not canonical JSON")
        if event.get("schema") != OPERATIONAL_EVENT_SCHEMA:
            self._integrity_failure("journal event schema mismatch")

        sequence = event.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            self._integrity_failure("journal event sequence is invalid")
        if sequence != row["sequence"]:
            self._integrity_failure("journal event sequence column mismatch")
        if expected_sequence is not None and sequence != expected_sequence:
            self._integrity_failure("journal sequence mismatch")

        kind = event.get("kind")
        if kind != row["kind"]:
            self._integrity_failure("journal event kind column mismatch")
        event_outbox = event.get("outbox_id")
        if event_outbox != row["outbox_id"]:
            self._integrity_failure("journal event outbox column mismatch")

        previous = event.get("previous_sha256")
        if previous != row["previous_sha256"]:
            self._integrity_failure(
                "journal event previous hash column mismatch"
            )
        if expected_previous is not None and previous != expected_previous:
            self._integrity_failure("journal previous hash mismatch")
        if not isinstance(previous, str) or _SHA256_RE.fullmatch(previous) is None:
            self._integrity_failure("journal previous hash is invalid")

        claimed = event.get("event_sha256")
        if claimed != row["event_sha256"]:
            self._integrity_failure("journal event hash column mismatch")
        if not isinstance(claimed, str) or _SHA256_RE.fullmatch(claimed) is None:
            self._integrity_failure("journal event hash is invalid")
        unsigned = {
            key: item for key, item in event.items() if key != "event_sha256"
        }
        if sha256_json(unsigned) != claimed:
            self._integrity_failure("journal event hash mismatch")

        if self._acknowledgement_target(event) != row[
            "acknowledges_outbox_id"
        ]:
            self._integrity_failure(
                "journal acknowledgement target column mismatch"
            )
        return event

    @staticmethod
    def _acknowledgement_target(event: Mapping[str, Any]) -> str | None:
        if event.get("kind") != "outbox.acknowledged":
            return None
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            return "None"
        return str(payload.get("outbox_id"))

    def _synchronize_integrity_locked(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        try:
            self._validate_database_identity_locked(connection)
        except OperationalJournalError as exc:
            self._integrity_failure(str(exc))
        data_version, schema_version = self._database_versions(connection)
        schema_changed = (
            self._observed_schema_version is not None
            and schema_version != self._observed_schema_version
        )
        data_changed = (
            self._observed_data_version is not None
            and data_version != self._observed_data_version
        )
        if schema_changed:
            try:
                self._validate_schema_objects_locked(connection)
            except OperationalJournalError as exc:
                self._integrity_failure(str(exc))
        if data_changed or schema_changed:
            self._verify_full_chain_locked(connection)
            self._observed_data_version = data_version
            self._observed_schema_version = schema_version
            return

        count, head = self._metadata_locked(connection)
        if count < self._verified_sequence:
            self._integrity_failure("journal event count moved backwards")
        if count == self._verified_sequence:
            if head != self._verified_head:
                self._integrity_failure("journal head metadata mismatch")
            if count == 0:
                unexpected = connection.execute(
                    "SELECT 1 FROM operational_events LIMIT 1"
                ).fetchone()
                if unexpected is not None:
                    self._integrity_failure(
                        "journal contains events behind an empty head"
                    )
                self._observed_data_version = data_version
                self._observed_schema_version = schema_version
                return
            head_row = connection.execute(
                f"SELECT {_EVENT_COLUMNS} FROM operational_events "
                "WHERE sequence = ?",
                (count,),
            ).fetchone()
            if head_row is None:
                self._integrity_failure("journal head event is missing")
            decoded = self._decode_row(
                cast(sqlite3.Row, head_row),
                expected_sequence=count,
            )
            if decoded["event_sha256"] != head:
                self._integrity_failure("journal head event hash mismatch")
            self._observed_data_version = data_version
            self._observed_schema_version = schema_version
            return

        previous = self._verified_head
        expected_sequence = self._verified_sequence + 1
        if self._verified_sequence:
            anchor = connection.execute(
                f"SELECT {_EVENT_COLUMNS} FROM operational_events "
                "WHERE sequence = ?",
                (self._verified_sequence,),
            ).fetchone()
            if anchor is None:
                self._integrity_failure("verified journal anchor is missing")
            anchor_event = self._decode_row(
                cast(sqlite3.Row, anchor),
                expected_sequence=self._verified_sequence,
            )
            if anchor_event["event_sha256"] != self._verified_head:
                self._integrity_failure("verified journal anchor changed")

        cursor = connection.execute(
            f"SELECT {_EVENT_COLUMNS} FROM operational_events "
            "WHERE sequence > ? ORDER BY sequence",
            (self._verified_sequence,),
        )
        observed = self._verified_sequence
        while True:
            rows = cursor.fetchmany(self._scan_batch_size)
            if not rows:
                break
            for row in rows:
                event = self._decode_row(
                    row,
                    expected_sequence=expected_sequence,
                    expected_previous=previous,
                )
                previous = str(event["event_sha256"])
                observed = expected_sequence
                expected_sequence += 1
        if observed != count:
            self._integrity_failure("journal metadata count mismatch")
        if previous != head:
            self._integrity_failure("journal metadata head mismatch")
        self._verified_sequence = count
        self._verified_head = head
        self._observed_data_version = data_version
        self._observed_schema_version = schema_version

    def _verify_full_chain_locked(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        quick_check = connection.execute("PRAGMA quick_check(1)").fetchone()
        if quick_check is None or str(quick_check[0]).casefold() != "ok":
            self._integrity_failure("SQLite quick_check failed")

        expected_sequence = 1
        previous = _ZERO_SHA256
        cursor = connection.execute(
            f"SELECT {_EVENT_COLUMNS} FROM operational_events "
            "ORDER BY sequence"
        )
        while True:
            rows = cursor.fetchmany(self._scan_batch_size)
            if not rows:
                break
            for row in rows:
                event = self._decode_row(
                    row,
                    expected_sequence=expected_sequence,
                    expected_previous=previous,
                )
                previous = str(event["event_sha256"])
                expected_sequence += 1
        observed_count = expected_sequence - 1
        metadata_count, metadata_head = self._metadata_locked(connection)
        if metadata_count != observed_count:
            self._integrity_failure("journal metadata count mismatch")
        if metadata_head != previous:
            self._integrity_failure("journal metadata head mismatch")
        self._verified_sequence = observed_count
        self._verified_head = previous

    def _metadata_locked(
        self,
        connection: sqlite3.Connection,
    ) -> tuple[int, str]:
        rows = connection.execute(
            "SELECT schema, event_count, head_sha256 "
            "FROM journal_metadata WHERE singleton = 1"
        ).fetchall()
        if len(rows) != 1:
            self._integrity_failure("journal metadata row is missing")
        row = rows[0]
        if row["schema"] != SQLITE_OPERATIONAL_JOURNAL_SCHEMA:
            self._integrity_failure("journal metadata schema mismatch")
        count = row["event_count"]
        head = row["head_sha256"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            self._integrity_failure("journal metadata count is invalid")
        if not isinstance(head, str) or _SHA256_RE.fullmatch(head) is None:
            self._integrity_failure("journal metadata head is invalid")
        if count == 0 and head != _ZERO_SHA256:
            self._integrity_failure("empty journal head is not zero")
        if count > 0 and head == _ZERO_SHA256:
            self._integrity_failure("non-empty journal head is zero")
        return count, head

    def _configure_connection(self, connection: sqlite3.Connection) -> None:
        timeout_ms = max(1, int(self._busy_timeout_seconds * 1000))
        connection.execute(f"PRAGMA busy_timeout = {timeout_ms}")
        mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()
        if mode is None or str(mode[0]).casefold() != "wal":
            raise OperationalJournalError(
                "SQLite refused WAL journal mode"
            )
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA fullfsync = ON")
        connection.execute("PRAGMA checkpoint_fullfsync = ON")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA trusted_schema = OFF")
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.execute(
            f"PRAGMA wal_autocheckpoint = {self._wal_autocheckpoint_pages}"
        )
        connection.execute(
            f"PRAGMA journal_size_limit = {self._journal_size_limit_bytes}"
        )

    def _initialize_or_validate_schema(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute("BEGIN IMMEDIATE")
        try:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            application_id = int(
                connection.execute("PRAGMA application_id").fetchone()[0]
            )
            user_version = int(
                connection.execute("PRAGMA user_version").fetchone()[0]
            )
            if not tables:
                if application_id not in (0, _APPLICATION_ID):
                    raise OperationalJournalError(
                        "SQLite application id mismatch"
                    )
                if user_version not in (0, _SCHEMA_VERSION):
                    raise OperationalJournalError(
                        "SQLite schema version mismatch"
                    )
                for _object_type, statement in _SCHEMA_OBJECTS.values():
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO journal_metadata "
                    "(singleton, schema, event_count, head_sha256) "
                    "VALUES (1, ?, 0, ?)",
                    (SQLITE_OPERATIONAL_JOURNAL_SCHEMA, _ZERO_SHA256),
                )
                connection.execute(f"PRAGMA application_id = {_APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            else:
                if application_id != _APPLICATION_ID:
                    raise OperationalJournalError(
                        "SQLite application id mismatch"
                    )
                if user_version != _SCHEMA_VERSION:
                    raise OperationalJournalError(
                        "SQLite schema version mismatch"
                    )
                if tables != {"journal_metadata", "operational_events"}:
                    raise OperationalJournalError(
                        "SQLite journal contains unexpected tables"
                    )
                self._validate_schema_objects_locked(connection)
            connection.execute("COMMIT")
        except BaseException:
            self._rollback_quietly(connection)
            raise

    def _validate_schema_objects_locked(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        named_objects = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type IN ('table', 'index', 'trigger', 'view') "
                "AND name NOT LIKE 'sqlite_%' "
                "AND sql IS NOT NULL"
            )
        }
        if named_objects != set(_SCHEMA_OBJECTS):
            unexpected = sorted(named_objects - set(_SCHEMA_OBJECTS))
            missing = sorted(set(_SCHEMA_OBJECTS) - named_objects)
            raise OperationalJournalError(
                "SQLite journal schema object set mismatch: "
                f"unexpected={unexpected}, missing={missing}"
            )
        rows = connection.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name IN ({})".format(
                ",".join("?" for _ in _SCHEMA_OBJECTS)
            ),
            tuple(_SCHEMA_OBJECTS),
        ).fetchall()
        actual = {
            str(row["name"]): (
                str(row["type"]),
                _normalized_sql(str(row["sql"])),
            )
            for row in rows
        }
        for name, (object_type, statement) in _SCHEMA_OBJECTS.items():
            expected = (object_type, _normalized_sql(statement))
            if actual.get(name) != expected:
                raise OperationalJournalError(
                    f"SQLite journal schema object mismatch: {name}"
                )

    @staticmethod
    def _validate_database_identity_locked(
        connection: sqlite3.Connection,
    ) -> None:
        application_id = int(
            connection.execute("PRAGMA application_id").fetchone()[0]
        )
        if application_id != _APPLICATION_ID:
            raise OperationalJournalError("SQLite application id mismatch")
        user_version = int(
            connection.execute("PRAGMA user_version").fetchone()[0]
        )
        if user_version != _SCHEMA_VERSION:
            raise OperationalJournalError("SQLite schema version mismatch")

    @staticmethod
    def _database_versions(
        connection: sqlite3.Connection,
    ) -> tuple[int, int]:
        data_version = int(
            connection.execute("PRAGMA data_version").fetchone()[0]
        )
        schema_version = int(
            connection.execute("PRAGMA schema_version").fetchone()[0]
        )
        return data_version, schema_version

    def _verification_state(
        self,
    ) -> tuple[int, str, int | None, int | None]:
        return (
            self._verified_sequence,
            self._verified_head,
            self._observed_data_version,
            self._observed_schema_version,
        )

    def _restore_verification_state(
        self,
        state: tuple[int, str, int | None, int | None],
    ) -> None:
        (
            self._verified_sequence,
            self._verified_head,
            self._observed_data_version,
            self._observed_schema_version,
        ) = state

    def _raise_if_unavailable(self) -> None:
        if self._closed:
            raise OperationalJournalError("operational journal is closed")
        if self._error is not None:
            raise OperationalJournalError(
                f"operational journal unhealthy: {self._error}"
            )

    def _require_connection(self) -> sqlite3.Connection:
        self._raise_if_unavailable()
        if self._connection is None:
            raise OperationalJournalError(
                "operational journal connection is unavailable"
            )
        return self._connection

    def _integrity_failure(self, message: str) -> NoReturn:
        self._error = f"OperationalJournalError: {message}"
        raise OperationalJournalError(message)

    def _poison_sqlite(
        self,
        message: str,
        exc: sqlite3.Error,
    ) -> NoReturn:
        self._error = f"{type(exc).__name__}: {exc}"
        raise OperationalJournalError(
            f"{message}: {type(exc).__name__}"
        ) from exc

    @staticmethod
    def _rollback_quietly(connection: sqlite3.Connection) -> None:
        try:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass


__all__ = [
    "SQLITE_OPERATIONAL_JOURNAL_SCHEMA",
    "SQLiteOperationalJournal",
]
