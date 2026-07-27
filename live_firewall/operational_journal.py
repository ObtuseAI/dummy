"""Compact append-only operational journal and durable outbox.

This journal is intentionally separate from Dummy's high-volume research
ledger.  It records only low-volume authority, reservation, bootstrap, and
reconciliation facts needed at the live boundary.  A broken hash chain is an
authority failure: callers can inspect the journal, but cannot append through
an unhealthy instance.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import contextmanager
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator, cast


OPERATIONAL_EVENT_SCHEMA = "dummy.operational-event.v1"


def canonical_json(value: Any) -> str:
    """Return the shared DumbMoney canonical JSON representation."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class OperationalJournalError(RuntimeError):
    """Raised when an append-only journal cannot prove its own history."""


class AppendOnlyOperationalJournal:
    """Hash-chained JSONL journal with serialized cross-process appends."""

    def __init__(
        self,
        path: Path,
        *,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._operation_lock = threading.RLock()
        self._lock_path = self.path.with_name(f"{self.path.name}.lock")
        self._operation_lock_path = self.path.with_name(
            f"{self.path.name}.operation.lock"
        )
        self._events: list[dict[str, Any]] = []
        self._error: str | None = None
        self._load()

    @property
    def healthy(self) -> bool:
        return self._error is None

    @property
    def error(self) -> str | None:
        return self._error

    def events(self, *, kind: str | None = None) -> tuple[dict[str, Any], ...]:
        with self._lock:
            self._refresh_or_raise()
            rows = list(self._events)
        if kind is not None:
            rows = [row for row in rows if row.get("kind") == kind]
        # Canonical round-trip prevents callers from mutating journal state.
        return tuple(json.loads(canonical_json(row)) for row in rows)

    def head(self) -> tuple[int, str]:
        """Return the verified monotonic sequence and chain head."""
        with self._lock:
            self._refresh_or_raise()
            if not self._events:
                return 0, "0" * 64
            latest = self._events[-1]
            return int(latest["sequence"]), str(latest["event_sha256"])

    def _load(self) -> None:
        try:
            with self._lock:
                with self._interprocess_lock():
                    self._reload_locked()
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"

    @staticmethod
    @contextmanager
    def _lock_file(handle: BinaryIO) -> Iterator[None]:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(  # type: ignore[attr-defined]
            handle.fileno(),
            fcntl.LOCK_EX,  # type: ignore[attr-defined]
        )
        try:
            yield
        finally:
            fcntl.flock(  # type: ignore[attr-defined]
                handle.fileno(),
                fcntl.LOCK_UN,  # type: ignore[attr-defined]
            )

    @contextmanager
    def _interprocess_lock(self) -> Iterator[None]:
        """Lock a stable sidecar byte for the full reload/append transaction."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
                os.fsync(handle.fileno())
            with self._lock_file(handle):
                yield

    @contextmanager
    def serialized_operation(self) -> Iterator[None]:
        """Serialize a caller-owned multi-step operation across processes.

        This lock is deliberately separate from the append lock so the caller
        may safely perform journal reads/appends while holding it.
        """
        with self._operation_lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._operation_lock_path.open("a+b") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                    os.fsync(handle.fileno())
                with self._lock_file(handle):
                    yield

    def _reload_locked(self) -> None:
        raw = self.path.read_bytes() if self.path.exists() else b""
        if raw and not raw.endswith(b"\n"):
            raise OperationalJournalError("journal has a partial trailing record")
        previous = "0" * 64
        expected_sequence = 1
        rows: list[dict[str, Any]] = []
        for line in raw.splitlines():
            if not line:
                raise OperationalJournalError("journal contains a blank record")
            value = json.loads(line.decode("utf-8"))
            if not isinstance(value, dict):
                raise OperationalJournalError("journal record must be an object")
            if value.get("schema") != OPERATIONAL_EVENT_SCHEMA:
                raise OperationalJournalError("journal schema mismatch")
            if value.get("sequence") != expected_sequence:
                raise OperationalJournalError("journal sequence mismatch")
            if value.get("previous_sha256") != previous:
                raise OperationalJournalError("journal previous hash mismatch")
            claimed = str(value.get("event_sha256") or "")
            unsigned = {
                key: item for key, item in value.items() if key != "event_sha256"
            }
            actual = sha256_json(unsigned)
            if claimed != actual:
                raise OperationalJournalError("journal event hash mismatch")
            # Reject non-canonical encodings so two readers cannot hash
            # semantically equivalent but byte-distinct histories.
            if line.decode("utf-8") != canonical_json(value):
                raise OperationalJournalError("journal record is not canonical JSON")
            rows.append(value)
            previous = claimed
            expected_sequence += 1
        self._events = rows

    def _refresh_or_raise(self) -> None:
        if self._error is not None:
            raise OperationalJournalError(
                f"operational journal unhealthy: {self._error}"
            )
        try:
            with self._interprocess_lock():
                self._reload_locked()
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            raise OperationalJournalError(
                f"operational journal refresh failed: {type(exc).__name__}"
            ) from exc

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
        """Append and fsync one fact.

        ``outbox_id`` is globally idempotent. Repeating the identical event
        returns the original event; reusing the id for different content fails.
        Callers acquiring one-shot authority may set
        ``allow_existing_outbox=False`` so even an identical prior event is a
        failed claim rather than apparent ownership.
        ``validate_existing`` runs against an immutable current snapshot while
        the cross-process writer lock is held, immediately before the append.
        It must not call back into this journal.
        When ``validate_existing_latest_kinds`` is supplied, that snapshot is
        bounded to at most the latest row for each named kind. Omitting it
        preserves the full-history callback contract.
        """
        with self._lock:
            if self._error is not None:
                raise OperationalJournalError(
                    f"operational journal unhealthy: {self._error}"
                )
            if not isinstance(kind, str) or not kind.strip():
                raise ValueError("journal kind is required")
            normalized_payload = json.loads(canonical_json(dict(payload)))
            normalized_outbox = str(outbox_id).strip() if outbox_id is not None else None
            if normalized_outbox == "":
                raise ValueError("outbox_id cannot be blank")
            normalized_latest_kinds: tuple[str, ...] | None = None
            if validate_existing_latest_kinds is not None:
                if validate_existing is None:
                    raise ValueError(
                        "validate_existing_latest_kinds requires "
                        "validate_existing"
                    )
                if not isinstance(validate_existing_latest_kinds, tuple):
                    raise TypeError(
                        "validate_existing_latest_kinds must be a tuple"
                    )
                if not 1 <= len(validate_existing_latest_kinds) <= 64:
                    raise ValueError(
                        "validate_existing_latest_kinds must contain "
                        "1 to 64 kinds"
                    )
                latest_kinds: list[str] = []
                for latest_kind in validate_existing_latest_kinds:
                    if (
                        not isinstance(latest_kind, str)
                        or not latest_kind.strip()
                    ):
                        raise ValueError(
                            "validation kind must be a non-blank string"
                        )
                    if latest_kind not in latest_kinds:
                        latest_kinds.append(latest_kind)
                normalized_latest_kinds = tuple(latest_kinds)
            try:
                with self._interprocess_lock():
                    try:
                        self._reload_locked()
                    except Exception as exc:
                        self._error = f"{type(exc).__name__}: {exc}"
                        raise OperationalJournalError(
                            "operational journal integrity refresh failed"
                        ) from exc
                    if normalized_outbox is not None:
                        existing = next(
                            (
                                row
                                for row in self._events
                                if row.get("outbox_id") == normalized_outbox
                            ),
                            None,
                        )
                        if existing is not None:
                            if not allow_existing_outbox:
                                raise OperationalJournalError(
                                    "outbox id is already claimed"
                                )
                            if (
                                existing.get("kind") == kind
                                and existing.get("payload") == normalized_payload
                            ):
                                return cast(
                                    dict[str, Any],
                                    json.loads(canonical_json(existing)),
                                )
                            raise OperationalJournalError(
                                "outbox id reused with different content"
                            )
                    if validate_existing is not None:
                        validation_rows = self._events
                        if normalized_latest_kinds is not None:
                            latest_by_kind: dict[str, dict[str, Any]] = {}
                            for row in self._events:
                                row_kind = row.get("kind")
                                if row_kind in normalized_latest_kinds:
                                    latest_by_kind[str(row_kind)] = row
                            validation_rows = sorted(
                                latest_by_kind.values(),
                                key=lambda row: int(row["sequence"]),
                            )
                        snapshot = tuple(
                            json.loads(canonical_json(row))
                            for row in validation_rows
                        )
                        validate_existing(snapshot)

                    now = self._now_fn()
                    if now.tzinfo is None or now.utcoffset() is None:
                        raise ValueError("journal clock must be timezone-aware")
                    event: dict[str, Any] = {
                        "schema": OPERATIONAL_EVENT_SCHEMA,
                        "sequence": len(self._events) + 1,
                        "recorded_at": now.astimezone(timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "kind": kind,
                        "payload": normalized_payload,
                        "previous_sha256": (
                            str(self._events[-1]["event_sha256"])
                            if self._events
                            else "0" * 64
                        ),
                    }
                    if normalized_outbox is not None:
                        event["outbox_id"] = normalized_outbox
                    event["event_sha256"] = sha256_json(event)
                    serialized = (canonical_json(event) + "\n").encode("utf-8")
                    try:
                        with self.path.open("ab") as journal_handle:
                            journal_handle.write(serialized)
                            journal_handle.flush()
                            os.fsync(journal_handle.fileno())
                    except OSError as exc:
                        self._error = f"{type(exc).__name__}: {exc}"
                        raise OperationalJournalError(
                            f"operational journal append failed: {type(exc).__name__}"
                        ) from exc
                    self._events.append(event)
            except OSError as exc:
                self._error = f"{type(exc).__name__}: {exc}"
                raise OperationalJournalError(
                    f"operational journal lock failed: {type(exc).__name__}"
                ) from exc
            return cast(
                dict[str, Any],
                json.loads(canonical_json(event)),
            )

    def acknowledge_outbox(
        self,
        outbox_id: str,
        *,
        acknowledgement: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = str(outbox_id).strip()
        rows = self.events()
        source = next(
            (row for row in rows if row.get("outbox_id") == normalized),
            None,
        )
        if source is None:
            raise OperationalJournalError("cannot acknowledge unknown outbox id")
        payload = {
            "outbox_id": normalized,
            "source_event_sha256": source["event_sha256"],
            "acknowledgement": dict(acknowledgement or {}),
        }
        return self.append(
            "outbox.acknowledged",
            payload,
            outbox_id=f"ack:{normalized}",
        )

    def pending_outbox(self) -> tuple[dict[str, Any], ...]:
        rows = self.events()
        acknowledged = {
            str(row.get("payload", {}).get("outbox_id"))
            for row in rows
            if row.get("kind") == "outbox.acknowledged"
        }
        return tuple(
            json.loads(canonical_json(row))
            for row in rows
            if row.get("outbox_id")
            and row.get("kind") != "outbox.acknowledged"
            and row["outbox_id"] not in acknowledged
        )


__all__ = [
    "AppendOnlyOperationalJournal",
    "OPERATIONAL_EVENT_SCHEMA",
    "OperationalJournalError",
    "canonical_json",
    "sha256_json",
]
