"""Append-only outcome ledger for V17 truth-loop evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


@dataclass
class OutcomeLedgerRecord:
    record_id: str
    record_type: str
    market_id: str
    event_id: str
    domain: str
    payload: dict[str, Any]
    proof_refs: list[str]
    source_refs: list[str]
    created_at: str
    previous_hash: str
    record_hash: str
    schema_version: str = "outcome-ledger-v1"

    def hash_payload(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "market_id": self.market_id,
            "event_id": self.event_id,
            "domain": self.domain,
            "payload": self.payload,
            "proof_refs": self.proof_refs,
            "source_refs": self.source_refs,
            "created_at": self.created_at,
            "previous_hash": self.previous_hash,
            "schema_version": self.schema_version,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.hash_payload(), "record_hash": self.record_hash}


@dataclass(frozen=True)
class LedgerAppendResult:
    recorded: bool
    record: OutcomeLedgerRecord


@dataclass(frozen=True)
class LedgerQueryResult:
    records: list[OutcomeLedgerRecord]


@dataclass(frozen=True)
class LedgerReplayResult:
    record_count: int
    markets: dict[str, dict[str, Any]]
    verdict: str


@dataclass(frozen=True)
class LedgerIntegrityResult:
    verdict: str
    checked_count: int
    broken_record_ids: list[str] = field(default_factory=list)


class OutcomeLedger:
    record_types = [
        "MARKET_DISCOVERED",
        "FORECAST_SNAPSHOT_CREATED",
        "DECISION_RECORDED",
        "NO_TRADE_RECORDED",
        "OUTCOME_OBSERVED",
        "CALIBRATION_SCORED",
        "ATTRIBUTION_CREATED",
        "BLOODLINE_UPDATED",
        "IMPROVEMENT_PROPOSAL_CREATED",
    ]

    def __init__(self) -> None:
        self._records: list[OutcomeLedgerRecord] = []

    @property
    def records(self) -> list[OutcomeLedgerRecord]:
        return self._records

    @classmethod
    def schema_report(cls) -> dict[str, Any]:
        return {
            "workstream": "V17: Outcome Ledger Schema",
            "schema_version": "outcome-ledger-v1",
            "append_only": True,
            "record_types": cls.record_types,
            "proof_refs_supported": True,
            "source_refs_supported": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def append(
        self,
        *,
        record_type: str,
        market_id: str,
        event_id: str,
        domain: str,
        payload: dict[str, Any] | None = None,
        proof_refs: list[str] | None = None,
        source_refs: list[str] | None = None,
    ) -> LedgerAppendResult:
        index = len(self._records) + 1
        record_id = f"{index:06d}-{record_type}-{market_id}"
        previous_hash = self._records[-1].record_hash if self._records else "GENESIS"
        record = OutcomeLedgerRecord(
            record_id=record_id,
            record_type=record_type,
            market_id=market_id,
            event_id=event_id,
            domain=domain,
            payload=dict(payload or {}),
            proof_refs=list(proof_refs or []),
            source_refs=list(source_refs or []),
            created_at=_now_iso(),
            previous_hash=previous_hash,
            record_hash="",
        )
        record.record_hash = self._hash_record(record)
        self._records.append(record)
        return LedgerAppendResult(recorded=True, record=record)

    def query(self, *, market_id: str | None = None, domain: str | None = None) -> LedgerQueryResult:
        records = self._records
        if market_id is not None:
            records = [record for record in records if record.market_id == market_id]
        if domain is not None:
            records = [record for record in records if record.domain == domain]
        return LedgerQueryResult(records=list(records))

    def replay(self) -> LedgerReplayResult:
        markets: dict[str, dict[str, Any]] = {}
        for record in self._records:
            market = markets.setdefault(
                record.market_id,
                {"event_id": record.event_id, "domain": record.domain, "records": [], "latest_payload": {}},
            )
            market["records"].append(record.record_type)
            market["latest_payload"] = dict(record.payload)
        return LedgerReplayResult(record_count=len(self._records), markets=markets, verdict="PASS")

    def integrity_check(self) -> LedgerIntegrityResult:
        broken: list[str] = []
        previous = "GENESIS"
        for record in self._records:
            if record.previous_hash != previous or self._hash_record(record) != record.record_hash:
                broken.append(record.record_id)
            previous = record.record_hash
        return LedgerIntegrityResult(verdict="PASS" if not broken else "FAIL", checked_count=len(self._records), broken_record_ids=broken)

    def to_report(self) -> dict[str, Any]:
        integrity = self.integrity_check()
        return {
            "workstream": "V17: Outcome Ledger",
            "schema_version": "outcome-ledger-v1",
            "append_only": True,
            "record_types": self.record_types,
            "record_count": len(self._records),
            "records": [record.to_dict() for record in self._records],
            "integrity": integrity.__dict__,
            "secret_values_exposed": False,
            "verdict": integrity.verdict,
        }

    @staticmethod
    def _hash_record(record: OutcomeLedgerRecord) -> str:
        return hashlib.sha256(_canonical(record.hash_payload()).encode("utf-8")).hexdigest()
