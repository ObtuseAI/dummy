"""Immutable evidence-linked projections for the Phase 7 observatory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from dummy.constitution import Authority
from dummy.organisms.models import freeze_json, iso, parse_iso, thaw_json
from dummy.world_model.models import digest_json


class ObservatoryPanel(str, Enum):
    COMMAND_CENTER = "command_center"
    FORECAST_ORGANISMS = "forecast_organisms"
    WORLD_MODELS = "world_models"
    CALIBRATION = "calibration"
    EXECUTION_TRUTH = "execution_truth"
    EVOLUTION = "evolution"
    HOMEOSTASIS = "homeostasis"
    CONSTITUTION = "constitution"


@dataclass(frozen=True, slots=True)
class EvidenceClaim:
    claim_id: str
    label: str
    value: Any
    status: str
    evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.label.strip() or not self.status.strip():
            raise ValueError("observatory claims require a label and status")
        evidence_ids = tuple(sorted(str(item).strip() for item in self.evidence_ids))
        limitations = tuple(sorted(str(item).strip() for item in self.limitations))
        if not evidence_ids or any(not item for item in evidence_ids):
            raise ValueError("every observatory claim must link evidence IDs")
        if any(not item for item in limitations) or len(limitations) != len(set(limitations)):
            raise ValueError("observatory limitations must be non-empty")
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(self, "value", freeze_json(self.value))
        if self.claim_id != digest_json(self.semantic_dict()):
            raise ValueError("observatory claim ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "label": self.label,
            "value": thaw_json(self.value),
            "status": self.status,
            "evidence_ids": list(self.evidence_ids),
            "limitations": list(self.limitations),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"claim_id": self.claim_id, **self.semantic_dict()}


@dataclass(frozen=True, slots=True)
class PanelProjection:
    panel: ObservatoryPanel
    claims: tuple[EvidenceClaim, ...]

    def __post_init__(self) -> None:
        claims = tuple(sorted(self.claims, key=lambda item: item.claim_id))
        if not claims or len({item.claim_id for item in claims}) != len(claims):
            raise ValueError("observatory panel requires unique claims")
        object.__setattr__(self, "claims", claims)

    def to_dict(self) -> dict[str, Any]:
        return {
            "panel": self.panel.value,
            "claim_count": len(self.claims),
            "claims": [item.to_dict() for item in self.claims],
        }


@dataclass(frozen=True, slots=True)
class ObservatorySnapshot:
    snapshot_id: str
    generated_at: datetime
    panels: tuple[PanelProjection, ...]
    source_artifacts: Mapping[str, str]
    telemetry_status: str
    authority: Authority = Authority.OBSERVE
    read_only: bool = True

    def __post_init__(self) -> None:
        generated_at = parse_iso(self.generated_at)
        panels = tuple(sorted(self.panels, key=lambda item: item.panel.value))
        if {item.panel for item in panels} != set(ObservatoryPanel):
            raise ValueError("observatory snapshot must contain every canonical panel")
        if self.authority is not Authority.OBSERVE or not self.read_only:
            raise ValueError("observatory snapshot must be read-only OBSERVE authority")
        if self.telemetry_status not in {
            "POINT_IN_TIME_SNAPSHOT_NO_LIVE_TELEMETRY",
            "POINT_IN_TIME_RUNTIME_TELEMETRY",
        }:
            raise ValueError("invalid observatory telemetry status")
        if not all(
            isinstance(key, str)
            and key.strip()
            and isinstance(value, str)
            and value.strip()
            for key, value in self.source_artifacts.items()
        ):
            raise ValueError("observatory source artifacts must be named paths")
        sources = freeze_json(self.source_artifacts)
        if not sources:
            raise ValueError("observatory snapshot requires source artifacts")
        object.__setattr__(self, "generated_at", generated_at)
        object.__setattr__(self, "panels", panels)
        object.__setattr__(self, "source_artifacts", sources)
        if self.snapshot_id != digest_json(self.semantic_dict()):
            raise ValueError("observatory snapshot ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "phase": 7,
            "generated_at": iso(self.generated_at),
            "panels": [item.to_dict() for item in self.panels],
            "source_artifacts": thaw_json(self.source_artifacts),
            "telemetry_status": self.telemetry_status,
            "authority": self.authority.name,
            "read_only": True,
            "write_actions": [],
            "execution_authority": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, **self.semantic_dict()}


__all__ = [
    "EvidenceClaim",
    "ObservatoryPanel",
    "ObservatorySnapshot",
    "PanelProjection",
]
