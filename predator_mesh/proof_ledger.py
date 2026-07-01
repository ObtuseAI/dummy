"""Mesh proof ledger for recording lane lifecycle and governance events."""

from __future__ import annotations

from datetime import datetime, timezone
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
