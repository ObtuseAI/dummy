"""Classify disagreement without assuming consensus means independence."""

from __future__ import annotations


def disagreement_state(
    probabilities: tuple[float, ...],
    source_families: tuple[str, ...],
) -> dict[str, object]:
    spread = max(probabilities) - min(probabilities) if probabilities else 1.0
    family_count = len(set(source_families))
    duplicate_count = max(0, len(source_families) - family_count)
    return {
        "forecast_spread": round(spread, 12),
        "source_count": len(probabilities),
        "family_count": family_count,
        "duplicate_family_count": duplicate_count,
        "interpretation": (
            "MATERIAL_DISAGREEMENT"
            if spread >= 0.20
            else "CONSENSUS_NOT_INDEPENDENCE_PROOF"
        ),
        "uncertainty_must_widen": spread >= 0.10,
    }
