"""Data inflow discovery, registry, and scoring."""

from __future__ import annotations

from predator_mesh.data_inflow.adapters import (
    BaseDataAdapter,
    FileSampleAdapter,
    KalshiReadOnlyAdapter,
    MockDataAdapter,
    RSSSampleAdapter,
)
from predator_mesh.data_inflow.models import (
    DataSourceCandidate,
    SourceCategory,
    SourceStatus,
)
from predator_mesh.data_inflow.registry import DataSourceRegistry
from predator_mesh.data_inflow.scoring import (
    DataSourceScore,
    SourceScorer,
    SourceTier,
)

__all__ = [
    "BaseDataAdapter",
    "DataSourceCandidate",
    "DataSourceRegistry",
    "DataSourceScore",
    "FileSampleAdapter",
    "KalshiReadOnlyAdapter",
    "MockDataAdapter",
    "RSSSampleAdapter",
    "SourceCategory",
    "SourceScorer",
    "SourceStatus",
    "SourceTier",
]
