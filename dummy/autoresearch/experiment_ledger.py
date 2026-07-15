"""Append-only, hash-chained experiment records for nested research."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dummy.world_model.models import canonical_json, digest_json

from .models import AutoresearchValidationError


GENESIS_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class ExperimentLedgerEntry:
    sequence: int
    previous_hash: str
    experiment_id: str
    payload: Mapping[str, Any]
    entry_hash: str

    def body(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "sequence": self.sequence,
            "previous_hash": self.previous_hash,
            "experiment_id": self.experiment_id,
            "payload": dict(self.payload),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.body(), "entry_hash": self.entry_hash}


class ExperimentLedger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read_verified(self) -> tuple[ExperimentLedgerEntry, ...]:
        if not self.path.exists():
            return ()
        entries: list[ExperimentLedgerEntry] = []
        previous = GENESIS_HASH
        seen: set[str] = set()
        for expected_sequence, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines()
        ):
            if not line.strip():
                continue
            data = json.loads(line)
            entry = ExperimentLedgerEntry(
                sequence=int(data["sequence"]),
                previous_hash=str(data["previous_hash"]),
                experiment_id=str(data["experiment_id"]),
                payload=dict(data["payload"]),
                entry_hash=str(data["entry_hash"]),
            )
            if entry.sequence != expected_sequence or entry.previous_hash != previous:
                raise AutoresearchValidationError("experiment ledger chain is broken")
            if entry.experiment_id in seen:
                raise AutoresearchValidationError("experiment ledger contains a duplicate")
            if entry.entry_hash != digest_json(entry.body()):
                raise AutoresearchValidationError("experiment ledger entry was tampered")
            entries.append(entry)
            seen.add(entry.experiment_id)
            previous = entry.entry_hash
        return tuple(entries)

    def append(
        self, experiment_id: str, payload: Mapping[str, Any]
    ) -> ExperimentLedgerEntry:
        if not experiment_id.strip():
            raise AutoresearchValidationError("experiment ID is required")
        entries = self.read_verified()
        if any(item.experiment_id == experiment_id for item in entries):
            raise AutoresearchValidationError("experiment ID already exists")
        sequence = len(entries)
        previous_hash = entries[-1].entry_hash if entries else GENESIS_HASH
        body = {
            "schema_version": 1,
            "sequence": sequence,
            "previous_hash": previous_hash,
            "experiment_id": experiment_id,
            "payload": dict(payload),
        }
        entry = ExperimentLedgerEntry(
            sequence=sequence,
            previous_hash=previous_hash,
            experiment_id=experiment_id,
            payload=dict(payload),
            entry_hash=digest_json(body),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(entry.to_dict()) + "\n")
        self.read_verified()
        return entry


__all__ = ["GENESIS_HASH", "ExperimentLedger", "ExperimentLedgerEntry"]
