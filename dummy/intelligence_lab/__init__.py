"""Protected research laboratory for discovering better cognitive methods."""

from .discovery import design_experiments, discover_opportunities, generate_hypotheses
from .engine import (
    baseline_cognitive_genome,
    intelligence_lab_manifest,
    run_intelligence_research_cycle,
)
from .forecast_domain import observe_forecasting_research
from .models import (
    CognitiveGenome,
    CognitiveHypothesis,
    CognitiveOperator,
    ExperimentProtocol,
    GraphKind,
    IntelligenceLabValidationError,
    ReplicationReceipt,
    ResearchOpportunity,
    ScientificObservation,
    TheoryMaturity,
    make_replication_receipt,
)
from .scientific_memory import ScientificMemory, ScientificMemoryEntry
from .theory import evaluate_theory

__all__ = [
    "CognitiveGenome",
    "CognitiveHypothesis",
    "CognitiveOperator",
    "ExperimentProtocol",
    "GraphKind",
    "IntelligenceLabValidationError",
    "ReplicationReceipt",
    "ResearchOpportunity",
    "ScientificMemory",
    "ScientificMemoryEntry",
    "ScientificObservation",
    "TheoryMaturity",
    "baseline_cognitive_genome",
    "design_experiments",
    "discover_opportunities",
    "evaluate_theory",
    "generate_hypotheses",
    "intelligence_lab_manifest",
    "make_replication_receipt",
    "observe_forecasting_research",
    "run_intelligence_research_cycle",
]
