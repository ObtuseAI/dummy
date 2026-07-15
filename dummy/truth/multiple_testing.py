"""Family-wise error control for evolutionary candidate searches."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .cluster_statistics import TruthValidationError


@dataclass(frozen=True, slots=True)
class CorrectedHypothesis:
    hypothesis_id: str
    raw_p_value: float
    adjusted_p_value: float
    threshold: float
    rejected_null: bool
    rank: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "raw_p_value": self.raw_p_value,
            "adjusted_p_value": self.adjusted_p_value,
            "threshold": self.threshold,
            "rejected_null": self.rejected_null,
            "rank": self.rank,
            "method": "HOLM_BONFERRONI",
        }


def holm_bonferroni(
    tests: tuple[tuple[str, float], ...],
    *,
    alpha: float = 0.05,
) -> tuple[CorrectedHypothesis, ...]:
    if not 0.0 < float(alpha) < 1.0:
        raise TruthValidationError("multiple-testing alpha must be in (0, 1)")
    ids = tuple(str(item[0]).strip() for item in tests)
    if any(not item for item in ids) or len(set(ids)) != len(ids):
        raise TruthValidationError("hypothesis IDs must be unique and non-empty")
    parsed = []
    for hypothesis_id, p_value in tests:
        value = float(p_value)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise TruthValidationError("raw p-values must be in [0, 1]")
        parsed.append((str(hypothesis_id), value))
    ordered = sorted(parsed, key=lambda item: (item[1], item[0]))
    count = len(ordered)
    running_adjusted = 0.0
    continue_rejecting = True
    results = []
    for index, (hypothesis_id, raw) in enumerate(ordered):
        multiplier = count - index
        running_adjusted = max(running_adjusted, min(1.0, multiplier * raw))
        threshold = alpha / multiplier
        rejected = continue_rejecting and raw <= threshold
        if not rejected:
            continue_rejecting = False
        results.append(
            CorrectedHypothesis(
                hypothesis_id=hypothesis_id,
                raw_p_value=raw,
                adjusted_p_value=round(running_adjusted, 12),
                threshold=round(threshold, 12),
                rejected_null=rejected,
                rank=index + 1,
            )
        )
    return tuple(sorted(results, key=lambda item: item.hypothesis_id))


__all__ = ["CorrectedHypothesis", "holm_bonferroni"]
