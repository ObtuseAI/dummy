"""Difficulty estimation that remains inert until settlement-calibrated."""

from __future__ import annotations

from .state import DifficultyEstimate, MetaCalibrationEvidence


def estimate_difficulty(
    *,
    completeness: float,
    forecast_spread: float,
    max_uncertainty: float,
    regime_familiarity: float,
    calibration: MetaCalibrationEvidence,
) -> DifficultyEstimate:
    components = (
        1.0 - completeness,
        min(1.0, 2.0 * forecast_spread),
        min(1.0, 2.0 * max_uncertainty),
        1.0 - regime_familiarity,
    )
    score = round(sum(components) / len(components), 12)
    band = "LOW" if score < 0.25 else "MEDIUM" if score < 0.5 else "HIGH" if score < 0.75 else "EXTREME"
    reasons = []
    labels = (
        "world_state_incomplete",
        "forecast_disagreement",
        "forecast_uncertainty",
        "regime_unfamiliar",
    )
    reasons.extend(label for label, value in zip(labels, components, strict=True) if value >= 0.25)
    if not reasons:
        reasons.append("no_material_difficulty_component")
    if not calibration.verified:
        reasons.append("difficulty_mapping_uncalibrated_shadow_only")
    return DifficultyEstimate(
        score=score,
        band=band,
        reasons=tuple(reasons),
        calibration=calibration,
    )
