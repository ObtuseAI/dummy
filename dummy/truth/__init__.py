"""DUMMY vNext causal truth, clustered inference, and claim correction."""

from .baseline_arbitration import BaselineSet
from .causal_attribution import causal_attribution_report
from .cluster_statistics import (
    ClusterStatistic,
    TruthValidationError,
    clustered_mean_test,
)
from .contested_truth import contested_rows
from .drift import drift_state
from .multiple_testing import CorrectedHypothesis, holm_bonferroni

__all__ = [
    "BaselineSet",
    "ClusterStatistic",
    "CorrectedHypothesis",
    "TruthValidationError",
    "causal_attribution_report",
    "clustered_mean_test",
    "contested_rows",
    "drift_state",
    "holm_bonferroni",
]
