"""DUMMY vNext calibrated, shadow-only metacognitive control."""

from .abstention import recommend_abstention
from .calibration import unavailable_meta_calibration
from .confidence import decompose_confidence
from .difficulty import estimate_difficulty
from .disagreement import disagreement_state
from .evaluator import evaluate_metacognition
from .evidence import (
    MetacognitiveEvaluationCase,
    abstention_value_report,
    confidence_calibration_report,
    resource_efficiency_report,
)
from .knowledge_boundary import classify_knowledge_boundary
from .meta_evolution import meta_policy_proposal
from .progress import recommend_stopping
from .resource_allocator import recommend_resources
from .state import (
    ConfidenceDecomposition,
    ControlAction,
    ControlRecommendation,
    DifficultyEstimate,
    KnowledgeBoundary,
    KnowledgeBoundaryAssessment,
    MetaCalibrationEvidence,
    MetaCalibrationState,
    MetacognitiveState,
    MetacognitiveValidationError,
)
from .strategy_selector import recommend_strategy

__all__ = [
    "ConfidenceDecomposition",
    "ControlAction",
    "ControlRecommendation",
    "DifficultyEstimate",
    "KnowledgeBoundary",
    "KnowledgeBoundaryAssessment",
    "MetaCalibrationEvidence",
    "MetaCalibrationState",
    "MetacognitiveState",
    "MetacognitiveEvaluationCase",
    "MetacognitiveValidationError",
    "classify_knowledge_boundary",
    "abstention_value_report",
    "confidence_calibration_report",
    "decompose_confidence",
    "disagreement_state",
    "estimate_difficulty",
    "evaluate_metacognition",
    "meta_policy_proposal",
    "recommend_abstention",
    "recommend_resources",
    "recommend_stopping",
    "recommend_strategy",
    "resource_efficiency_report",
    "unavailable_meta_calibration",
]
