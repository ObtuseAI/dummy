"""DUMMY vNext protected, proposal-only recursive evolution engine."""

from .archive import EvolutionArchive
from .candidate import CandidateEvaluationInput, EvolutionEvaluationCase
from .challenger import EvolutionChallenger
from .evaluator import EVALUATOR_VERSION, evaluate_evolution_family
from .meta_evolution import propose_meta_policy_challenger
from .mutation_operators import bounded_numeric_operations
from .population import CandidatePopulation, build_population
from .promotion import promotion_proposal
from .rollback import rollback_proposal

__all__ = [
    "EVALUATOR_VERSION",
    "CandidateEvaluationInput",
    "CandidatePopulation",
    "EvolutionArchive",
    "EvolutionChallenger",
    "EvolutionEvaluationCase",
    "bounded_numeric_operations",
    "build_population",
    "evaluate_evolution_family",
    "promotion_proposal",
    "propose_meta_policy_challenger",
    "rollback_proposal",
]
