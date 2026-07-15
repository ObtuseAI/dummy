"""Role-specific minimum sufficient context with private-data redaction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from dummy.world_model.models import canonical_json, digest_json

from .models import AutoresearchValidationError, ResearchRole


_ALLOWLISTS: dict[ResearchRole, tuple[str, ...]] = {
    ResearchRole.FORECASTER: (
        "current_market_state",
        "world_model",
        "recent_analogues",
        "active_features",
        "prior_forecast",
        "unresolved_uncertainties",
    ),
    ResearchRole.ADVERSARY: (
        "frozen_forecast",
        "evidence_and_assumptions",
        "strongest_counterexamples",
        "market_prior",
        "known_failure_modes",
    ),
    ResearchRole.CALIBRATOR: (
        "probability",
        "calibration_bucket",
        "regime",
        "source_family",
        "sample_size",
        "historical_reliability",
    ),
    ResearchRole.EVOLUTION_DEBUGGER: (
        "failing_artifact",
        "relevant_code",
        "current_champion",
        "compact_lineage_summary",
        "newest_decisions",
        "relevant_failures",
        "historical_attempts",
        "private_aggregate_receipt",
    ),
}

_PRIVATE_ITEM_KEYS = frozenset(
    {
        "private_cases",
        "private_tasks",
        "private_outcomes",
        "private_probabilities",
        "private_case_ids",
        "trap_identity_by_case",
        "hidden_dates",
        "hidden_teams",
        "hidden_symbols",
        "hidden_strikes",
    }
)


@dataclass(frozen=True, slots=True)
class DistilledContext:
    context_id: str
    role: ResearchRole
    payload: Mapping[str, Any]
    original_characters: int
    distilled_characters: int
    compression_ratio: float
    max_characters: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "role": self.role.value,
            "payload": dict(self.payload),
            "original_characters": self.original_characters,
            "distilled_characters": self.distilled_characters,
            "compression_ratio": round(self.compression_ratio, 12),
            "max_characters": self.max_characters,
            "private_item_details": None,
        }


def _find_forbidden(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in _PRIVATE_ITEM_KEYS:
                found.add(normalized)
            found.update(_find_forbidden(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found.update(_find_forbidden(nested))
    return found


def distill_context(
    role: ResearchRole,
    source: Mapping[str, Any],
    *,
    max_characters: int = 8_000,
) -> DistilledContext:
    if max_characters < 256:
        raise AutoresearchValidationError("context budget is too small")
    forbidden = _find_forbidden(source)
    if forbidden:
        raise AutoresearchValidationError(
            f"private item-level context is forbidden: {sorted(forbidden)}"
        )
    original = canonical_json(dict(source))
    payload: dict[str, Any] = {
        key: source[key] for key in _ALLOWLISTS[role] if key in source
    }
    if not payload:
        raise AutoresearchValidationError("no role-relevant context was supplied")
    for history_key in (
        "historical_attempts",
        "relevant_failures",
        "newest_decisions",
        "recent_analogues",
    ):
        if history_key in payload and isinstance(payload[history_key], (list, tuple)):
            payload[history_key] = list(payload[history_key])[-32:]
    serialized = canonical_json(payload)
    removable = (
        "historical_attempts",
        "recent_analogues",
        "relevant_failures",
        "newest_decisions",
    )
    while len(serialized) > max_characters:
        changed = False
        for key in removable:
            rows = payload.get(key)
            if isinstance(rows, list) and len(rows) > 1:
                payload[key] = rows[len(rows) // 2 :]
                serialized = canonical_json(payload)
                changed = True
                break
        if not changed:
            raise AutoresearchValidationError(
                "minimum sufficient role context exceeds its budget"
            )
    ratio = len(original) / max(1, len(serialized))
    semantic = {
        "schema_version": 1,
        "role": role.value,
        "payload": json.loads(serialized),
        "original_characters": len(original),
        "distilled_characters": len(serialized),
        "compression_ratio": round(ratio, 12),
        "max_characters": max_characters,
        "private_item_details": None,
    }
    return DistilledContext(
        context_id=digest_json(semantic),
        role=role,
        payload=json.loads(serialized),
        original_characters=len(original),
        distilled_characters=len(serialized),
        compression_ratio=ratio,
        max_characters=max_characters,
    )


def context_policy_manifest() -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": 1,
        "role_allowlists": {
            role.value: list(fields) for role, fields in _ALLOWLISTS.items()
        },
        "target_compression_ratio": 16.0,
        "target_is_measurement_not_claim": True,
        "current_champion_full_definition_preserved": True,
        "history_policy": "hash_and_one_line_outcome_except_relevant_failures",
        "private_item_details_forbidden": sorted(_PRIVATE_ITEM_KEYS),
    }
    body["manifest_id"] = digest_json(body)
    return body


__all__ = ["DistilledContext", "context_policy_manifest", "distill_context"]
