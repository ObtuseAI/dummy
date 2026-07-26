"""Transactional, content-addressed, hash-chained research journal."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from dummy.world_model.models import canonical_json, digest_json

from .models import AutoresearchValidationError, iso, utc


GENESIS_HASH = "0" * 64
SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class JournalEvent:
    sequence: int
    event_id: str
    event_type: str
    subject_id: str
    semantic_key: str
    occurred_at: datetime
    payload: Mapping[str, Any]
    previous_hash: str
    entry_hash: str

    def body(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "sequence": self.sequence,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "subject_id": self.subject_id,
            "semantic_key": self.semantic_key,
            "occurred_at": iso(self.occurred_at),
            "payload": dict(self.payload),
            "previous_hash": self.previous_hash,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.body(), "entry_hash": self.entry_hash}


class ResearchJournal:
    """SQLite journal with atomic deduplication and a verified event chain."""

    def __init__(self, path: Path, *, timeout_seconds: float = 10.0) -> None:
        self.path = Path(path)
        self.timeout_seconds = float(timeout_seconds)
        if self.timeout_seconds <= 0:
            raise AutoresearchValidationError("journal timeout must be positive")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self.read_events_verified()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=self.timeout_seconds,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(f"PRAGMA busy_timeout={int(self.timeout_seconds * 1000)}")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS research_definitions (
                    record_id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    stored_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_events (
                    sequence INTEGER PRIMARY KEY,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    semantic_key TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS idx_research_events_lookup
                    ON research_events(event_type, semantic_key);
                CREATE INDEX IF NOT EXISTS idx_research_events_subject
                    ON research_events(subject_id, sequence);
                CREATE TRIGGER IF NOT EXISTS research_definitions_immutable_update
                BEFORE UPDATE ON research_definitions
                BEGIN
                    SELECT RAISE(ABORT, 'research definitions are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS research_definitions_immutable_delete
                BEFORE DELETE ON research_definitions
                BEGIN
                    SELECT RAISE(ABORT, 'research definitions are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS research_events_immutable_update
                BEFORE UPDATE ON research_events
                BEGIN
                    SELECT RAISE(ABORT, 'research events are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS research_events_immutable_delete
                BEFORE DELETE ON research_events
                BEGIN
                    SELECT RAISE(ABORT, 'research events are immutable');
                END;
                """
            )

    @staticmethod
    def _validate_identity(record_id: str, semantic: Mapping[str, Any]) -> None:
        if record_id != digest_json(dict(semantic)):
            raise AutoresearchValidationError(
                "research record identity does not match semantic content"
            )

    def store_definition(
        self,
        *,
        record_id: str,
        record_type: str,
        semantic: Mapping[str, Any],
        stored_at: datetime,
    ) -> bool:
        """Store a semantic definition exactly once.

        The definition and its chain event are committed in the same
        ``BEGIN IMMEDIATE`` transaction, so concurrent writers cannot both
        claim the same definition or fork the chain.
        """
        normalized_type = str(record_type).strip()
        if not normalized_type:
            raise AutoresearchValidationError("record_type is required")
        normalized = dict(semantic)
        self._validate_identity(record_id, normalized)
        semantic_json = canonical_json(normalized)
        timestamp = iso(stored_at)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT record_type, semantic_json
                FROM research_definitions
                WHERE record_id = ?
                """,
                (record_id,),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["record_type"]) != normalized_type
                    or str(existing["semantic_json"]) != semantic_json
                ):
                    connection.rollback()
                    raise AutoresearchValidationError(
                        "research definition identity was reused with different content"
                    )
                connection.commit()
                return False
            connection.execute(
                """
                INSERT INTO research_definitions(
                    record_id, record_type, semantic_json, stored_at
                ) VALUES (?, ?, ?, ?)
                """,
                (record_id, normalized_type, semantic_json, timestamp),
            )
            payload = {
                "record_id": record_id,
                "record_type": normalized_type,
                "semantic_digest": digest_json(normalized),
            }
            event_id = digest_json(payload)
            self._append_event_in_transaction(
                connection,
                event_id=event_id,
                event_type="DEFINITION_STORED",
                subject_id=record_id,
                semantic_key=record_id,
                occurred_at=utc(stored_at),
                payload=payload,
            )
            connection.commit()
            return True

    def append_event(
        self,
        *,
        event_id: str,
        event_type: str,
        subject_id: str,
        semantic_key: str,
        occurred_at: datetime,
        payload: Mapping[str, Any],
    ) -> tuple[JournalEvent, bool]:
        normalized_payload = dict(payload)
        if event_id != digest_json(normalized_payload):
            raise AutoresearchValidationError(
                "journal event ID must address its immutable payload"
            )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT * FROM research_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
            if existing is not None:
                event = self._event_from_row(existing)
                if event.payload != normalized_payload:
                    connection.rollback()
                    raise AutoresearchValidationError(
                        "journal event identity was reused with different content"
                    )
                connection.commit()
                return event, False
            event = self._append_event_in_transaction(
                connection,
                event_id=event_id,
                event_type=event_type,
                subject_id=subject_id,
                semantic_key=semantic_key,
                occurred_at=occurred_at,
                payload=normalized_payload,
            )
            connection.commit()
            return event, True

    def _append_event_in_transaction(
        self,
        connection: sqlite3.Connection,
        *,
        event_id: str,
        event_type: str,
        subject_id: str,
        semantic_key: str,
        occurred_at: datetime,
        payload: Mapping[str, Any],
    ) -> JournalEvent:
        for value, field in (
            (event_type, "event_type"),
            (subject_id, "subject_id"),
            (semantic_key, "semantic_key"),
        ):
            if not str(value).strip():
                raise AutoresearchValidationError(f"{field} is required")
        tip = connection.execute(
            """
            SELECT sequence, entry_hash
            FROM research_events
            ORDER BY sequence DESC
            LIMIT 1
            """
        ).fetchone()
        sequence = int(tip["sequence"]) + 1 if tip is not None else 0
        previous_hash = str(tip["entry_hash"]) if tip is not None else GENESIS_HASH
        event = JournalEvent(
            sequence=sequence,
            event_id=event_id,
            event_type=str(event_type),
            subject_id=str(subject_id),
            semantic_key=str(semantic_key),
            occurred_at=utc(occurred_at),
            payload=dict(payload),
            previous_hash=previous_hash,
            entry_hash="",
        )
        event = JournalEvent(
            sequence=event.sequence,
            event_id=event.event_id,
            event_type=event.event_type,
            subject_id=event.subject_id,
            semantic_key=event.semantic_key,
            occurred_at=event.occurred_at,
            payload=event.payload,
            previous_hash=event.previous_hash,
            entry_hash=digest_json(event.body()),
        )
        connection.execute(
            """
            INSERT INTO research_events(
                sequence, event_id, event_type, subject_id, semantic_key,
                occurred_at, payload_json, previous_hash, entry_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.sequence,
                event.event_id,
                event.event_type,
                event.subject_id,
                event.semantic_key,
                iso(event.occurred_at),
                canonical_json(event.payload),
                event.previous_hash,
                event.entry_hash,
            ),
        )
        return event

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> JournalEvent:
        return JournalEvent(
            sequence=int(row["sequence"]),
            event_id=str(row["event_id"]),
            event_type=str(row["event_type"]),
            subject_id=str(row["subject_id"]),
            semantic_key=str(row["semantic_key"]),
            occurred_at=utc(str(row["occurred_at"])),
            payload=json.loads(str(row["payload_json"])),
            previous_hash=str(row["previous_hash"]),
            entry_hash=str(row["entry_hash"]),
        )

    def read_events_verified(self) -> tuple[JournalEvent, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM research_events ORDER BY sequence"
            ).fetchall()
            definitions = connection.execute(
                """
                SELECT record_id, semantic_json
                FROM research_definitions
                ORDER BY record_id
                """
            ).fetchall()
        for row in definitions:
            semantic = json.loads(str(row["semantic_json"]))
            self._validate_identity(str(row["record_id"]), semantic)
        previous_hash = GENESIS_HASH
        events: list[JournalEvent] = []
        for expected_sequence, row in enumerate(rows):
            event = self._event_from_row(row)
            if (
                event.sequence != expected_sequence
                or event.previous_hash != previous_hash
            ):
                raise AutoresearchValidationError("research journal chain is broken")
            if event.event_id != digest_json(event.payload):
                raise AutoresearchValidationError(
                    "research journal event identity is invalid"
                )
            if event.entry_hash != digest_json(event.body()):
                raise AutoresearchValidationError("research journal was tampered")
            events.append(event)
            previous_hash = event.entry_hash
        return tuple(events)

    def find_event(
        self,
        *,
        event_type: str,
        semantic_key: str,
    ) -> JournalEvent | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM research_events
                WHERE event_type = ? AND semantic_key = ?
                ORDER BY sequence DESC
                LIMIT 1
                """,
                (event_type, semantic_key),
            ).fetchone()
        if row is None:
            return None
        event = self._event_from_row(row)
        if event.event_id != digest_json(event.payload):
            raise AutoresearchValidationError(
                "research journal event identity is invalid"
            )
        return event

    def candidate_events(self, candidate_id: str) -> tuple[JournalEvent, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM research_events
                WHERE event_type = 'CANDIDATE_STATE' AND subject_id = ?
                ORDER BY sequence
                """,
                (candidate_id,),
            ).fetchall()
        return tuple(self._event_from_row(row) for row in rows)

    def subject_events(
        self,
        subject_id: str,
        *,
        event_type: str | None = None,
    ) -> tuple[JournalEvent, ...]:
        with self._connect() as connection:
            if event_type is None:
                rows = connection.execute(
                    """
                    SELECT * FROM research_events
                    WHERE subject_id = ?
                    ORDER BY sequence
                    """,
                    (subject_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM research_events
                    WHERE subject_id = ? AND event_type = ?
                    ORDER BY sequence
                    """,
                    (subject_id, event_type),
                ).fetchall()
        return tuple(self._event_from_row(row) for row in rows)

    def checkpoint(self, *, occurred_at: datetime) -> JournalEvent:
        events = self.read_events_verified()
        payload = {
            "schema_version": 1,
            "checkpointed_sequence": events[-1].sequence if events else -1,
            "checkpointed_entry_hash": (
                events[-1].entry_hash if events else GENESIS_HASH
            ),
            "event_count": len(events),
            "occurred_at": iso(occurred_at),
        }
        event, _ = self.append_event(
            event_id=digest_json(payload),
            event_type="CHECKPOINT",
            subject_id="research-journal",
            semantic_key=payload["checkpointed_entry_hash"],
            occurred_at=occurred_at,
            payload=payload,
        )
        return event

    def summary(self) -> dict[str, Any]:
        events = self.read_events_verified()
        with self._connect() as connection:
            definitions = int(
                connection.execute(
                    "SELECT COUNT(*) FROM research_definitions"
                ).fetchone()[0]
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "definition_count": definitions,
            "event_count": len(events),
            "last_sequence": events[-1].sequence if events else -1,
            "tip_hash": events[-1].entry_hash if events else GENESIS_HASH,
            "verified": True,
        }


__all__ = ["GENESIS_HASH", "JournalEvent", "ResearchJournal"]
