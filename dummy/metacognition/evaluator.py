"""Build one complete shadow-only metacognitive state."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from dummy.metabolism import MarginalUtility
from dummy.protocols import MessageEnvelope, MessageType
from dummy.shadows import ShadowReview
from dummy.synthesis import SynthesisResult

from .abstention import recommend_abstention
from .confidence import decompose_confidence
from .difficulty import estimate_difficulty
from .disagreement import disagreement_state
from .knowledge_boundary import classify_knowledge_boundary
from .progress import recommend_stopping
from .resource_allocator import recommend_resources
from .state import MetaCalibrationEvidence, MetacognitiveState
from .strategy_selector import recommend_strategy


def evaluate_metacognition(
    *,
    world_state: Mapping[str, object],
    messages: tuple[MessageEnvelope, ...],
    decision_at: datetime,
    incumbent_calibration_verified: bool,
    meta_calibration: MetaCalibrationEvidence,
    shadow_review: ShadowReview,
    synthesis: SynthesisResult,
    marginal_utility: MarginalUtility,
) -> MetacognitiveState:
    forecasts = tuple(
        message
        for message in messages
        if message.message_type in {MessageType.FORECAST, MessageType.COUNTERFORECAST}
    )
    probabilities = tuple(float(message.payload["probability"]) for message in forecasts)
    uncertainties = tuple(float(message.payload.get("uncertainty", 0.5)) for message in forecasts)
    families = tuple(str(message.payload.get("source_family", "")) for message in forecasts)
    disagreement = disagreement_state(probabilities, families)
    confidence = decompose_confidence(
        world_state=world_state,
        messages=messages,
        decision_at=decision_at,
        incumbent_calibration_verified=incumbent_calibration_verified,
        meta_calibration=meta_calibration,
    )
    knowledge = classify_knowledge_boundary(
        completeness=float(world_state.get("completeness", 0.0)),
        forecast_spread=float(disagreement["forecast_spread"]),
        regime_familiarity=confidence.regime_familiarity,
        shadow_review=shadow_review,
    )
    difficulty = estimate_difficulty(
        completeness=confidence.evidence_completeness,
        forecast_spread=float(disagreement["forecast_spread"]),
        max_uncertainty=max(uncertainties, default=0.5),
        regime_familiarity=confidence.regime_familiarity,
        calibration=meta_calibration,
    )
    return MetacognitiveState(
        difficulty=difficulty,
        confidence=confidence,
        knowledge_boundary=knowledge,
        disagreement=disagreement,
        strategy=recommend_strategy(knowledge, meta_calibration),
        abstention=recommend_abstention(
            synthesis=synthesis,
            confidence=confidence,
            knowledge=knowledge,
            shadow_review=shadow_review,
            calibration=meta_calibration,
        ),
        stopping=recommend_stopping(
            utility=marginal_utility,
            shadow_review=shadow_review,
            calibration=meta_calibration,
        ),
        resource_allocation=recommend_resources(marginal_utility),
    )
