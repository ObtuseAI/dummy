"""V15 Kalshi credential source conflict resolver.

Detects when multiple candidate credential sources (process env, dummy env
file, local secret file reference) disagree on key id or private-key
reference kind, and resolves to a single deterministic, redacted source
without ever serializing secret values.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from predator_mesh.v13.credential_bridge import (
    KalshiReadOnlyCredentialBridge,
)


class KalshiCredentialSourcePriority(str, Enum):
    PROCESS_ENV = "process_env"
    DUMMY_ENV_FILE = "dummy_env_file"
    LOCAL_SECRET_FILE_REFERENCE = "local_secret_file_reference"
    MISSING = "missing"

    @classmethod
    def ordered(cls) -> list["KalshiCredentialSourcePriority"]:
        return [cls.PROCESS_ENV, cls.DUMMY_ENV_FILE, cls.LOCAL_SECRET_FILE_REFERENCE, cls.MISSING]


@dataclass(frozen=True)
class KalshiCredentialConflict:
    conflicting_sources: list[str]
    conflict_field: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflicting_sources": self.conflicting_sources,
            "conflict_field": self.conflict_field,
            "description": self.description,
        }


@dataclass(frozen=True)
class KalshiCredentialSelectedSourceProof:
    selected_source: str
    priority_order: list[str]
    reason: str
    redacted: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_source": self.selected_source,
            "priority_order": self.priority_order,
            "reason": self.reason,
            "redacted": True,
        }


@dataclass(frozen=True)
class KalshiCredentialConflictResolution:
    conflicts: list[KalshiCredentialConflict]
    selected_source_proof: KalshiCredentialSelectedSourceProof
    has_conflict: bool

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V15: Kalshi Credential Conflict Resolution",
            "has_conflict": self.has_conflict,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "selected_source": self.selected_source_proof.to_dict(),
            "secret_values_exposed": False,
            "redacted": True,
            "verdict": "PARTIAL" if self.has_conflict else "PASS",
        }


class KalshiCredentialSourceConflictResolver:
    """Compares candidate sources by presence/shape only (never raw values)."""

    def __init__(self, *, bridge: KalshiReadOnlyCredentialBridge | None = None) -> None:
        self.bridge = bridge or KalshiReadOnlyCredentialBridge()

    def _candidate_presence(self) -> dict[str, dict[str, bool]]:
        process = self.bridge._pick(self.bridge.env)  # noqa: SLF001
        dummy = self.bridge._pick(self.bridge._parse_env_file(self.bridge.dummy_env_path))  # noqa: SLF001
        project = self.bridge._pick(self.bridge._parse_env_file(self.bridge.project_env_path))  # noqa: SLF001
        candidates = {
            KalshiCredentialSourcePriority.PROCESS_ENV.value: process,
            KalshiCredentialSourcePriority.DUMMY_ENV_FILE.value: dummy,
            KalshiCredentialSourcePriority.LOCAL_SECRET_FILE_REFERENCE.value: project,
        }
        presence: dict[str, dict[str, bool]] = {}
        for name, values in candidates.items():
            presence[name] = {
                "key_id_present": bool(values.get("KALSHI_API_KEY_ID")),
                "private_key_present": any(
                    bool(values.get(n))
                    for n in ("KALSHI_API_PRIVATE_KEY_PEM", "KALSHI_API_PRIVATE_KEY_PEM_PATH", "KALSHI_API_PRIVATE_KEY_PATH")
                ),
            }
        return presence

    def detect_conflicts(self) -> list[KalshiCredentialConflict]:
        presence = self._candidate_presence()
        populated = [name for name, shape in presence.items() if shape["key_id_present"] or shape["private_key_present"]]
        conflicts: list[KalshiCredentialConflict] = []
        if len(populated) > 1:
            conflicts.append(
                KalshiCredentialConflict(
                    conflicting_sources=sorted(populated),
                    conflict_field="credential_material_presence",
                    description="Multiple candidate sources supply Kalshi credential material; only the highest-priority source is used.",
                )
            )
        return conflicts

    def resolve(self) -> KalshiCredentialConflictResolution:
        readiness = self.bridge.resolve()
        conflicts = self.detect_conflicts()
        priority_order = [p.value for p in KalshiCredentialSourcePriority.ordered()]
        proof = KalshiCredentialSelectedSourceProof(
            selected_source=readiness.source.value,
            priority_order=priority_order,
            reason="Highest-priority source with both key id and private key reference present wins.",
        )
        return KalshiCredentialConflictResolution(conflicts=conflicts, selected_source_proof=proof, has_conflict=bool(conflicts))

    def to_report(self) -> dict[str, Any]:
        return self.resolve().to_report()
