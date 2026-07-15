"""Deterministic rollback proposals preserve the last healthy research state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dummy.world_model.models import digest_json


def rollback_proposal(
    *,
    current_genome_id: str,
    target_genome_id: str,
    trigger: str,
    last_healthy_fitness_id: str,
    evidence_ids: tuple[str, ...],
    decided_at: datetime,
) -> dict[str, Any]:
    if current_genome_id == target_genome_id:
        raise ValueError("rollback target must differ from current genome")
    if any(
        not value.strip()
        for value in (
            current_genome_id,
            target_genome_id,
            trigger,
            last_healthy_fitness_id,
        )
    ):
        raise ValueError("rollback identity and trigger are required")
    if decided_at.tzinfo is None or decided_at.utcoffset() is None:
        raise ValueError("rollback time must be timezone-aware")
    evidence = tuple(sorted(str(item).strip() for item in evidence_ids))
    if not evidence or any(not item for item in evidence):
        raise ValueError("rollback evidence is required")
    body: dict[str, Any] = {
        "schema_version": 1,
        "current_genome_id": current_genome_id,
        "target_genome_id": target_genome_id,
        "trigger": trigger,
        "last_healthy_fitness_id": last_healthy_fitness_id,
        "evidence_ids": list(evidence),
        "decided_at": decided_at.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "reversible": True,
        "authority_direction": "CONTRACTION_ONLY",
        "execution_authority": False,
        "promotion_authority": "HUMAN_ONLY",
        "applied": False,
    }
    body["rollback_id"] = digest_json(body)
    return body


__all__ = ["rollback_proposal"]
