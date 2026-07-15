"""Bridge marginal utility into recommendation-only resource state."""

from __future__ import annotations

from dummy.metabolism import MarginalUtility, allocation_recommendation


def recommend_resources(utility: MarginalUtility) -> dict[str, object]:
    return allocation_recommendation(utility)
