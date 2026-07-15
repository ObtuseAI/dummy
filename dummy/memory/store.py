"""Append-only, hash-chained storage for causal memory records."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Iterable, Mapping, Protocol

from dummy.world_model.models import canonical_json, digest_json

from .schema import MemoryKind, MemoryRecord, MemoryValidationError


GENESIS_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class MemoryLedgerEntry:
    sequence: int
    previous_entry_hash: str
    record: MemoryRecord
    entry_hash: str

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise MemoryValidationError("memory ledger sequence must be positive")
        if len(self.previous_entry_hash) != 64:
            raise MemoryValidationError("previous memory entry hash is invalid")
        expected = digest_json(self.semantic_dict())
        if self.entry_hash != expected:
            raise MemoryValidationError("memory ledger entry hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        previous_entry_hash: str,
        record: MemoryRecord,
    ) -> MemoryLedgerEntry:
        semantic = {
            "schema_version": 1,
            "sequence": sequence,
            "previous_entry_hash": previous_entry_hash,
            "record": record.to_dict(),
        }
        return cls(
            sequence=sequence,
            previous_entry_hash=previous_entry_hash,
            record=record,
            entry_hash=digest_json(semantic),
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "sequence": self.sequence,
            "previous_entry_hash": self.previous_entry_hash,
            "record": self.record.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_dict(), "entry_hash": self.entry_hash}

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MemoryLedgerEntry:
        return cls(
            sequence=int(data["sequence"]),
            previous_entry_hash=str(data["previous_entry_hash"]),
            record=MemoryRecord.from_dict(data["record"]),
            entry_hash=str(data["entry_hash"]),
        )


class MemorySink(Protocol):
    def append(self, record: MemoryRecord) -> str: ...


def _validate_append(
    entries: tuple[MemoryLedgerEntry, ...],
    record: MemoryRecord,
) -> MemoryLedgerEntry | None:
    existing = tuple(item for item in entries if item.record.memory_id == record.memory_id)
    if existing:
        if len(existing) != 1 or existing[0].record.to_json() != record.to_json():
            raise MemoryValidationError("memory ID collision has different content")
        return None
    known = {item.record.memory_id for item in entries}
    missing = tuple(parent for parent in record.causal_parent_ids if parent not in known)
    if missing:
        raise MemoryValidationError(f"unknown causal memory parents: {list(missing)}")
    if entries and record.recorded_at < entries[-1].record.recorded_at:
        raise MemoryValidationError("memory append would move recorded time backwards")
    previous = entries[-1].entry_hash if entries else GENESIS_HASH
    return MemoryLedgerEntry.create(
        sequence=len(entries) + 1,
        previous_entry_hash=previous,
        record=record,
    )


def _verify(entries: tuple[MemoryLedgerEntry, ...]) -> None:
    known: set[str] = set()
    previous = GENESIS_HASH
    previous_time = None
    for expected_sequence, entry in enumerate(entries, start=1):
        if entry.sequence != expected_sequence or entry.previous_entry_hash != previous:
            raise MemoryValidationError("memory ledger chain is discontinuous")
        if entry.record.memory_id in known:
            raise MemoryValidationError("memory ledger contains duplicate IDs")
        if any(parent not in known for parent in entry.record.causal_parent_ids):
            raise MemoryValidationError("memory ledger contains a forward causal parent")
        if previous_time is not None and entry.record.recorded_at < previous_time:
            raise MemoryValidationError("memory ledger recorded time moves backwards")
        known.add(entry.record.memory_id)
        previous = entry.entry_hash
        previous_time = entry.record.recorded_at


class InMemoryMemoryLedger:
    def __init__(self) -> None:
        self._entries: list[MemoryLedgerEntry] = []

    def append(self, record: MemoryRecord) -> str:
        entry = _validate_append(tuple(self._entries), record)
        if entry is not None:
            self._entries.append(entry)
        return record.memory_id

    def append_many(self, records: Iterable[MemoryRecord]) -> tuple[str, ...]:
        return tuple(self.append(record) for record in records)

    def entries(self) -> tuple[MemoryLedgerEntry, ...]:
        entries = tuple(self._entries)
        _verify(entries)
        return entries

    def records(self, kind: MemoryKind | None = None) -> tuple[MemoryRecord, ...]:
        return tuple(
            item.record
            for item in self.entries()
            if kind is None or item.record.kind is kind
        )

    def get(self, memory_id: str) -> MemoryRecord:
        matches = tuple(item for item in self.records() if item.memory_id == memory_id)
        if len(matches) != 1:
            raise MemoryValidationError(f"unknown memory_id: {memory_id}")
        return matches[0]

    def head_hash(self) -> str:
        entries = self.entries()
        return entries[-1].entry_hash if entries else GENESIS_HASH


class JsonlMemoryLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def _entries(self) -> tuple[MemoryLedgerEntry, ...]:
        if not self.path.exists():
            return ()
        entries = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                raw = line.rstrip("\n")
                if not raw:
                    raise MemoryValidationError(
                        f"blank memory ledger row at line {line_number}"
                    )
                try:
                    entry = MemoryLedgerEntry.from_dict(json.loads(raw))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise MemoryValidationError(
                        f"invalid memory ledger row at line {line_number}"
                    ) from exc
                if raw != entry.to_json():
                    raise MemoryValidationError(
                        f"noncanonical memory ledger row at line {line_number}"
                    )
                entries.append(entry)
        result = tuple(entries)
        _verify(result)
        return result

    def append(self, record: MemoryRecord) -> str:
        with self._lock:
            entries = self._entries()
            entry = _validate_append(entries, record)
            if entry is None:
                return record.memory_id
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(entry.to_json())
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        return record.memory_id

    def append_many(self, records: Iterable[MemoryRecord]) -> tuple[str, ...]:
        return tuple(self.append(record) for record in records)

    def entries(self) -> tuple[MemoryLedgerEntry, ...]:
        return self._entries()

    def records(self, kind: MemoryKind | None = None) -> tuple[MemoryRecord, ...]:
        return tuple(
            item.record
            for item in self.entries()
            if kind is None or item.record.kind is kind
        )

    def get(self, memory_id: str) -> MemoryRecord:
        matches = tuple(item for item in self.records() if item.memory_id == memory_id)
        if len(matches) != 1:
            raise MemoryValidationError(f"unknown memory_id: {memory_id}")
        return matches[0]

    def head_hash(self) -> str:
        entries = self.entries()
        return entries[-1].entry_hash if entries else GENESIS_HASH


__all__ = [
    "GENESIS_HASH",
    "InMemoryMemoryLedger",
    "JsonlMemoryLedger",
    "MemoryLedgerEntry",
    "MemorySink",
]
