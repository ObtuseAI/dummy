"""Protected nested forecast research improvement loop for DUMMY vNext."""

from .candidate_minimizer import MinimizationDecision, select_minimized_candidate
from .complexity_gate import (
    ComplexityBudget,
    ComplexityDecision,
    evaluate_complexity,
    pareto_dominates,
)
from .context_distiller import DistilledContext, distill_context
from .experiment_ledger import ExperimentLedger, ExperimentLedgerEntry
from .external_evaluator import evaluate_external_generalization
from .ignition_test import (
    IgnitionLevel,
    IgnitionReport,
    IgnitionTrial,
    evaluate_ignition,
)
from .inner_organism import InnerForecastOrganism
from .lineage_bandit import LineageAllocation, LineageState, allocate_lineage
from .models import (
    AutoresearchValidationError,
    ComplexityProfile,
    EvaluationPartition,
    EvaluationSummary,
    MetricVector,
    PrivateEvaluationReceipt,
    ResearchPolicy,
    ResearchRole,
    ResearchTask,
    TaskSuite,
)
from .orchestrator import CandidateLifecycleResult, run_candidate_lifecycle
from .outer_researcher import (
    OuterEvolutionResearcher,
    ResearchBudget,
    ResearchExperiment,
)
from .private_evaluator import evaluate_private_selection
from .public_evaluator import evaluate_visible_development
from .reward_hacking_detector import (
    RewardHackAudit,
    RewardHackFinding,
    RewardHackTrap,
    audit_reward_hacking,
)
from .stall_fork import StallFork, propose_stall_fork
from .task_suite import build_task_suite

__all__ = [
    "AutoresearchValidationError",
    "CandidateLifecycleResult",
    "ComplexityBudget",
    "ComplexityDecision",
    "ComplexityProfile",
    "DistilledContext",
    "EvaluationPartition",
    "EvaluationSummary",
    "ExperimentLedger",
    "ExperimentLedgerEntry",
    "IgnitionLevel",
    "IgnitionReport",
    "IgnitionTrial",
    "InnerForecastOrganism",
    "LineageAllocation",
    "LineageState",
    "MetricVector",
    "MinimizationDecision",
    "OuterEvolutionResearcher",
    "PrivateEvaluationReceipt",
    "ResearchBudget",
    "ResearchExperiment",
    "ResearchPolicy",
    "ResearchRole",
    "ResearchTask",
    "RewardHackAudit",
    "RewardHackFinding",
    "RewardHackTrap",
    "StallFork",
    "TaskSuite",
    "allocate_lineage",
    "audit_reward_hacking",
    "build_task_suite",
    "distill_context",
    "evaluate_complexity",
    "evaluate_external_generalization",
    "evaluate_ignition",
    "evaluate_private_selection",
    "evaluate_visible_development",
    "pareto_dominates",
    "propose_stall_fork",
    "run_candidate_lifecycle",
    "select_minimized_candidate",
]
