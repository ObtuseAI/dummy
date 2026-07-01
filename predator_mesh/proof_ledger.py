"""Mesh proof ledger for recording lane lifecycle and governance events."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.models import MeshProofRef


class MeshProofLedger:
    """In-memory proof ledger with redaction-safe records."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.proof_refs: list[MeshProofRef] = []

    def record(
        self,
        event: str,
        lane: str | None = None,
        proof_ref: MeshProofRef | None = None,
        **extra: Any,
    ) -> MeshProofRef:
        """Record a mesh event and return its proof reference."""
        ref = proof_ref or MeshProofRef(
            component=lane or "mesh",
            verdict=event,
        )
        entry = {
            "event": event,
            "lane": lane,
            "ref_id": ref.ref_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "verdict": ref.verdict,
            "payload_hash": ref.payload_hash,
        }
        # Extra metadata is stored but should never contain secrets or raw prompts.
        for key, value in extra.items():
            if key not in entry:
                entry[key] = value
        self.events.append(entry)
        self.proof_refs.append(ref)
        return ref

    def count(self, event: str | None = None, lane: str | None = None) -> int:
        """Count events matching optional filters."""
        return sum(
            1
            for e in self.events
            if (event is None or e.get("event") == event)
            and (lane is None or e.get("lane") == lane)
        )

    def has_event(self, event: str, lane: str | None = None) -> bool:
        """Return True if at least one matching event was recorded."""
        return any(
            e.get("event") == event and (lane is None or e.get("lane") == lane)
            for e in self.events
        )

    def list_events(
        self,
        event: str | None = None,
        lane: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return a copy of matching events."""
        return [
            e
            for e in self.events
            if (event is None or e.get("event") == event)
            and (lane is None or e.get("lane") == lane)
        ]

    def summarize(self) -> dict[str, Any]:
        """Return a lightweight summary of all recorded events."""
        event_counts: dict[str, int] = {}
        lane_counts: dict[str, int] = {}
        for event in self.events:
            name = event.get("event") or "unknown"
            event_counts[name] = event_counts.get(name, 0) + 1
            lane = event.get("lane") or "mesh"
            lane_counts[lane] = lane_counts.get(lane, 0) + 1

        return {
            "event_count": len(self.events),
            "event_summary": event_counts,
            "lane_summary": lane_counts,
            "events": self.events,
        }

    def to_report(self) -> dict[str, Any]:
        """Return the ``mesh_proof_ledger_report_v1`` report dict."""
        summary = self.summarize()
        return {
            "report_type": "mesh_proof_ledger_report_v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "event_count": len(self.events),
            "event_summary": summary["event_summary"],
            "lane_summary": summary["lane_summary"],
            "events": self.events,
        }

    def write_report(
        self,
        path: str | Path = "artifacts/dummy/mesh_proof_ledger_report_v1.json",
    ) -> Path:
        """Write the proof ledger report to disk and return the path."""
        report_path = Path(path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(self.to_report(), indent=2, default=str),
            encoding="utf-8",
        )
        return report_path
