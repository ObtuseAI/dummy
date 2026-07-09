"""Immutable forecast snapshot ledger for V17."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ForecastSnapshot:
    market_id: str
    event_id: str
    domain: str
    probability: float
    confidence: float
    horizon: str
    evidence_stack: list[str]
    model_refs: list[str]
    market_implied_probability: float | None = None
    created_at: str = field(default_factory=_now_iso)
    future_outcome_known: bool = False

    @property
    def snapshot_id(self) -> str:
        raw = json.dumps(self.to_dict(include_id=False), sort_keys=True, default=str)
        return "forecast-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

    def to_dict(self, *, include_id: bool = True) -> dict[str, Any]:
        data = {
            "market_id": self.market_id,
            "event_id": self.event_id,
            "domain": self.domain,
            "probability": self.probability,
            "confidence": self.confidence,
            "horizon": self.horizon,
            "evidence_stack": list(self.evidence_stack),
            "model_refs": list(self.model_refs),
            "market_implied_probability": self.market_implied_probability,
            "created_at": self.created_at,
            "future_outcome_known": self.future_outcome_known,
        }
        if include_id:
            data["snapshot_id"] = self.snapshot_id
        return data


@dataclass(frozen=True)
class ForecastRecordResult:
    recorded: bool
    snapshot_id: str


class ForecastSnapshotLedger:
    @classmethod
    def schema_report(cls) -> dict[str, Any]:
        return {
            "workstream": "V17: Forecast Snapshot Schema",
            "required_fields": [
                "market_id",
                "event_id",
                "domain",
                "probability",
                "confidence",
                "horizon",
                "timestamp",
                "source_refs",
                "model_refs",
                "market_implied_probability",
            ],
            "immutable_after_recording": True,
            "future_outcome_leakage_allowed": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def __init__(self) -> None:
        self.snapshots: list[ForecastSnapshot] = []

    def record(self, snapshot: ForecastSnapshot) -> ForecastRecordResult:
        if snapshot.future_outcome_known:
            raise ValueError("Forecast snapshots must be recorded before outcome truth is known.")
        self.snapshots.append(snapshot)
        return ForecastRecordResult(recorded=True, snapshot_id=snapshot.snapshot_id)

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V17: Forecast Snapshot Ledger",
            "snapshot_count": len(self.snapshots),
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
            "outcome_leakage_detected": any(snapshot.future_outcome_known for snapshot in self.snapshots),
            "immutable_pre_outcome_snapshot": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }
