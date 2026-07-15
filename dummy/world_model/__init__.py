"""DUMMY vNext immutable, versioned world-model surface."""

from .adapters import hydrate_issue_world_state, observations_from_issue
from .builder import build_world_snapshot
from .evaluation import (
    WorldModelEvaluationCase,
    regime_transfer_report,
    world_state_ablation_report,
)
from .models import (
    ContradictionSeverity,
    MissingDataPolicy,
    ProvenanceRecord,
    StateLayer,
    ValueStatus,
    WorldContradiction,
    WorldDomain,
    WorldFieldSpec,
    WorldHydrationError,
    WorldModelValidationError,
    WorldObservation,
    WorldStateSchema,
    WorldStateSnapshot,
    WorldStateStaleError,
    WorldStateValue,
)
from .schemas import schema_for, supported_schema_manifest

__all__ = [
    "ContradictionSeverity",
    "MissingDataPolicy",
    "ProvenanceRecord",
    "StateLayer",
    "ValueStatus",
    "WorldContradiction",
    "WorldDomain",
    "WorldFieldSpec",
    "WorldHydrationError",
    "WorldModelEvaluationCase",
    "WorldModelValidationError",
    "WorldObservation",
    "WorldStateSchema",
    "WorldStateSnapshot",
    "WorldStateStaleError",
    "WorldStateValue",
    "build_world_snapshot",
    "hydrate_issue_world_state",
    "observations_from_issue",
    "regime_transfer_report",
    "schema_for",
    "supported_schema_manifest",
    "world_state_ablation_report",
]
