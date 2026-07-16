"""Append-only, tamper-evident ledger for autonomous fusion-membership changes.

Every autonomous promotion, stage escalation, and demotion the
``AutoPromotionEngine`` (autonomy/auto_promotion.py) decides is recorded here
before it takes effect. The record carries the FULL evidence dossier snapshot
(every threshold value beside the measured value that cleared or breached it),
so a later audit can reconstruct exactly why fusion membership changed without
trusting any mutable state.

The chain mirrors ``dummy/intelligence_lab/scientific_memory.py`` exactly:

  * one JSON object per line, in append order;
  * each entry stamps ``sequence`` (0-based), ``previous_hash`` (the prior
    entry's ``entry_hash``, ``GENESIS_HASH`` for the first), and ``entry_hash``
    (sha256 over the canonical body);
  * ``read_verified`` re-walks the chain and raises on any broken link,
    tampered body, or out-of-order sequence -- a corrupt ledger fails closed
    (the caller treats a raised chain as "no trustworthy history", which blocks
    new promotions via the daily-cap rail rather than silently proceeding).

Unlike scientific memory this ledger is a pure event log (not content-
addressed by identity): the same scope can legitimately be promoted, demoted,
and re-promoted over time, so each append is always a NEW sequence entry.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

GENESIS_HASH = "0" * 64

# Governance actions this ledger records.
ACTION_PROMOTE = "PROMOTE"          # challenger scope enters fusion at stage 1
ACTION_ESCALATE = "ESCALATE"        # promoted scope moves stage 1 -> stage 2
ACTION_DEMOTE = "DEMOTE"            # promoted scope removed from fusion
ACTION_ABORT = "ABORT"             # a promotion run aborted on a rail
VALID_ACTIONS = frozenset(
    {ACTION_PROMOTE, ACTION_ESCALATE, ACTION_DEMOTE, ACTION_ABORT}
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _digest(data: Any) -> str:
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


class PromotionLedgerError(Exception):
    """Raised when the hash chain is broken or an append is malformed."""


@dataclass(frozen=True, slots=True)
class PromotionLedgerEntry:
    sequence: int
    previous_hash: str
    action: str
    scope: str
    at: str
    payload: Mapping[str, Any]
    entry_hash: str

    def body(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "sequence": self.sequence,
            "previous_hash": self.previous_hash,
            "action": self.action,
            "scope": self.scope,
            "at": self.at,
            "payload": dict(self.payload),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.body(), "entry_hash": self.entry_hash}


class PromotionLedger:
    """A hash-chained JSONL log of autonomous fusion-membership changes."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def read_verified(self) -> tuple[PromotionLedgerEntry, ...]:
        """Return every entry, raising ``PromotionLedgerError`` on any break."""
        if not self.path.exists():
            return ()
        entries: list[PromotionLedgerEntry] = []
        previous = GENESIS_HASH
        sequence = 0
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PromotionLedgerError("promotion ledger line is not JSON") from exc
            try:
                entry = PromotionLedgerEntry(
                    sequence=int(value["sequence"]),
                    previous_hash=str(value["previous_hash"]),
                    action=str(value["action"]),
                    scope=str(value["scope"]),
                    at=str(value["at"]),
                    payload=dict(value["payload"]),
                    entry_hash=str(value["entry_hash"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise PromotionLedgerError("promotion ledger entry is malformed") from exc
            if entry.sequence != sequence or entry.previous_hash != previous:
                raise PromotionLedgerError("promotion ledger chain is broken")
            if entry.entry_hash != _digest(entry.body()):
                raise PromotionLedgerError("promotion ledger entry was tampered")
            entries.append(entry)
            previous = entry.entry_hash
            sequence += 1
        return tuple(entries)

    def append(
        self,
        *,
        action: str,
        scope: str,
        payload: Mapping[str, Any],
        at: str | None = None,
    ) -> PromotionLedgerEntry:
        """Append one governance record and return it.

        Verifies the existing chain first (fail-closed: a corrupt ledger cannot
        be silently extended). The new entry links to the last verified hash.
        """
        if action not in VALID_ACTIONS:
            raise PromotionLedgerError(f"unknown promotion action: {action!r}")
        if not str(scope).strip():
            raise PromotionLedgerError("promotion ledger scope is required")
        entries = self.read_verified()
        previous = entries[-1].entry_hash if entries else GENESIS_HASH
        body = {
            "schema_version": 1,
            "sequence": len(entries),
            "previous_hash": previous,
            "action": str(action),
            "scope": str(scope),
            "at": at or _now_iso(),
            "payload": dict(payload),
        }
        entry = PromotionLedgerEntry(
            sequence=len(entries),
            previous_hash=previous,
            action=str(action),
            scope=str(scope),
            at=body["at"],
            payload=dict(payload),
            entry_hash=_digest(body),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(_canonical(entry.to_dict()) + "\n")
        return entry

    def entries_on_date(self, iso_date: str) -> list[PromotionLedgerEntry]:
        """Entries whose ``at`` timestamp falls on the given YYYY-MM-DD (UTC).

        Used by the daily-cap rail. A broken chain raises, which the caller
        treats as "history untrustworthy" -> abort (fail-closed).
        """
        target = str(iso_date)[:10]
        return [e for e in self.read_verified() if str(e.at)[:10] == target]


__all__ = [
    "GENESIS_HASH",
    "ACTION_PROMOTE",
    "ACTION_ESCALATE",
    "ACTION_DEMOTE",
    "ACTION_ABORT",
    "VALID_ACTIONS",
    "PromotionLedger",
    "PromotionLedgerEntry",
    "PromotionLedgerError",
]
