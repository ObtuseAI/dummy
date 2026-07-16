"""Append-only scientific memory with tamper-evident causal history."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dummy.world_model.models import canonical_json, digest_json

from .models import IntelligenceLabValidationError


GENESIS_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class ScientificMemoryEntry:
    sequence: int
    previous_hash: str
    record_id: str
    record_type: str
    payload: Mapping[str, Any]
    entry_hash: str

    def body(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "sequence": self.sequence,
            "previous_hash": self.previous_hash,
            "record_id": self.record_id,
            "record_type": self.record_type,
            "payload": dict(self.payload),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.body(), "entry_hash": self.entry_hash}


class ScientificMemory:
    """A ledger of observations, failures, experiments, and theories.

    Re-appending an identical content-addressed record is an idempotent no-op.
    Reusing an ID with different content is impossible because the payload digest
    is checked before append.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def read_verified(self) -> tuple[ScientificMemoryEntry, ...]:
        if not self.path.exists():
            return ()
        entries: list[ScientificMemoryEntry] = []
        previous = GENESIS_HASH
        seen: set[str] = set()
        sequence = 0
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            entry = ScientificMemoryEntry(
                sequence=int(value["sequence"]),
                previous_hash=str(value["previous_hash"]),
                record_id=str(value["record_id"]),
                record_type=str(value["record_type"]),
                payload=dict(value["payload"]),
                entry_hash=str(value["entry_hash"]),
            )
            if entry.sequence != sequence or entry.previous_hash != previous:
                raise IntelligenceLabValidationError("scientific-memory chain is broken")
            if entry.record_id in seen:
                raise IntelligenceLabValidationError("scientific-memory record is duplicated")
            if entry.entry_hash != digest_json(entry.body()):
                raise IntelligenceLabValidationError("scientific-memory entry was tampered")
            if entry.record_id != digest_json(entry.payload):
                raise IntelligenceLabValidationError("scientific-memory record identity is invalid")
            entries.append(entry)
            seen.add(entry.record_id)
            previous = entry.entry_hash
            sequence += 1
        return tuple(entries)

    def append_unique(
        self,
        *,
        record_type: str,
        payload: Mapping[str, Any],
    ) -> tuple[ScientificMemoryEntry, bool]:
        normalized_type = record_type.strip()
        if not normalized_type:
            raise IntelligenceLabValidationError("record_type is required")
        normalized_payload = dict(payload)
        record_id = digest_json(normalized_payload)
        entries = self.read_verified()
        existing = next((item for item in entries if item.record_id == record_id), None)
        if existing is not None:
            return existing, False
        previous = entries[-1].entry_hash if entries else GENESIS_HASH
        body = {
            "schema_version": 1,
            "sequence": len(entries),
            "previous_hash": previous,
            "record_id": record_id,
            "record_type": normalized_type,
            "payload": normalized_payload,
        }
        entry = ScientificMemoryEntry(
            sequence=len(entries),
            previous_hash=previous,
            record_id=record_id,
            record_type=normalized_type,
            payload=normalized_payload,
            entry_hash=digest_json(body),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(entry.to_dict()) + "\n")
        self.read_verified()
        return entry, True


__all__ = ["GENESIS_HASH", "ScientificMemory", "ScientificMemoryEntry"]
