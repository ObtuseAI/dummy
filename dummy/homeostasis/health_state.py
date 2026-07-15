"""Deterministic aggregate health state for the vNext ecology."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from dummy.homeostasis.variables import HealthPolicy, HealthReading, HealthVariable
from dummy.world_model.models import digest_json


class HealthLevel(IntEnum):
    HEALTHY = 0
    ELEVATED = 1
    WARNING = 2
    CRITICAL = 3
    UNKNOWN = 4


@dataclass(frozen=True, slots=True)
class VariableHealth:
    variable: HealthVariable
    level: HealthLevel
    reading: HealthReading
    policy: HealthPolicy
    reason: str

    def __post_init__(self) -> None:
        if self.reading.variable is not self.variable or self.policy.variable is not self.variable:
            raise ValueError("health result variable mismatch")
        if not self.reason.strip():
            raise ValueError("health result reason must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable": self.variable.value,
            "level": self.level.name,
            "reading": self.reading.to_dict(),
            "policy": self.policy.to_dict(),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class HomeostasisState:
    state_id: str
    variables: tuple[VariableHealth, ...]
    overall_level: HealthLevel
    evidence_ids: tuple[str, ...]
    authority_expansion_allowed: bool = False

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.variables, key=lambda item: item.variable.value))
        if not ordered or len({item.variable for item in ordered}) != len(ordered):
            raise ValueError("homeostasis state requires unique variable results")
        if self.overall_level is not max(item.level for item in ordered):
            raise ValueError("overall health level must equal the worst variable level")
        evidence_ids = tuple(sorted({item for result in ordered for item in result.reading.evidence_ids}))
        if evidence_ids != tuple(self.evidence_ids):
            raise ValueError("homeostasis evidence IDs do not match variable evidence")
        if self.authority_expansion_allowed:
            raise ValueError("homeostasis cannot expand authority")
        object.__setattr__(self, "variables", ordered)
        if self.state_id != digest_json(self.semantic_dict()):
            raise ValueError("homeostasis state ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "variables": [item.to_dict() for item in self.variables],
            "overall_level": self.overall_level.name,
            "evidence_ids": list(self.evidence_ids),
            "authority_expansion_allowed": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"state_id": self.state_id, **self.semantic_dict()}


__all__ = ["HealthLevel", "HomeostasisState", "VariableHealth"]
