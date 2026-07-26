"""Protected nested forecast research improvement loop for DUMMY vNext."""

from .candidate_minimizer import MinimizationDecision, select_minimized_candidate
from .candidate_replay import (
    GenomeReplayPolicy,
    materialize_forward_tasks,
    materialize_task_suite,
    measure_genome_complexity,
)
from .campaign import run_loop1_campaign
from .complexity_gate import (
    ComplexityBudget,
    ComplexityDecision,
    evaluate_complexity,
    pareto_dominates,
)
from .control_models import (
    CandidateStage,
    CandidateStateEvent,
    EvaluationReceipt,
    EvaluationVerdict,
    EvidenceSnapshot,
    ResearchBudgetPolicy,
    ResearchDefinition,
    ResearchKind,
    ResearchRun,
    RunStatus,
)
from .context_distiller import DistilledContext, distill_context
from .experiment_ledger import ExperimentLedger, ExperimentLedgerEntry
from .external_evaluator import evaluate_external_generalization
from .forward_paper import (
    build_forward_registry,
    grade_forward_observations,
    issue_forward_observations,
)
from .ignition_test import (
    IgnitionLevel,
    IgnitionReport,
    IgnitionTrial,
    evaluate_ignition,
)
from .inner_organism import InnerForecastOrganism
from .lineage_bandit import LineageAllocation, LineageState, allocate_lineage
from .ledger_pipeline import (
    LedgerEvidenceRow,
    LedgerPartitionPlan,
    build_ledger_partition_plan,
    load_ledger_evidence,
)
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
from .operational_ignition import (
    operational_ignition_report,
    record_campaign_ignition_trial,
)
from .research_coordinator import (
    CoordinationResult,
    ResearchCoordinator,
    consume_intelligence_queue,
)
from .research_journal import JournalEvent, ResearchJournal
from .research_plugins import (
    evolution_definition,
    evolution_evidence_snapshot,
    intelligence_definition_from_protocol,
    intelligence_evidence_snapshot,
    plugin_manifest,
)
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
    "CandidateStage",
    "CandidateStateEvent",
    "CandidateLifecycleResult",
    "ComplexityBudget",
    "ComplexityDecision",
    "ComplexityProfile",
    "DistilledContext",
    "CoordinationResult",
    "EvaluationReceipt",
    "EvaluationPartition",
    "EvaluationSummary",
    "EvaluationVerdict",
    "EvidenceSnapshot",
    "ExperimentLedger",
    "ExperimentLedgerEntry",
    "GenomeReplayPolicy",
    "IgnitionLevel",
    "IgnitionReport",
    "IgnitionTrial",
    "InnerForecastOrganism",
    "LineageAllocation",
    "LineageState",
    "JournalEvent",
    "LedgerEvidenceRow",
    "LedgerPartitionPlan",
    "MetricVector",
    "MinimizationDecision",
    "OuterEvolutionResearcher",
    "PrivateEvaluationReceipt",
    "ResearchBudget",
    "ResearchBudgetPolicy",
    "ResearchCoordinator",
    "ResearchDefinition",
    "ResearchExperiment",
    "ResearchJournal",
    "ResearchKind",
    "ResearchPolicy",
    "ResearchRun",
    "ResearchRole",
    "ResearchTask",
    "RewardHackAudit",
    "RewardHackFinding",
    "RewardHackTrap",
    "StallFork",
    "RunStatus",
    "TaskSuite",
    "allocate_lineage",
    "audit_reward_hacking",
    "build_forward_registry",
    "build_ledger_partition_plan",
    "build_task_suite",
    "consume_intelligence_queue",
    "distill_context",
    "evaluate_complexity",
    "evaluate_external_generalization",
    "evaluate_ignition",
    "evaluate_private_selection",
    "evaluate_visible_development",
    "evolution_definition",
    "evolution_evidence_snapshot",
    "grade_forward_observations",
    "issue_forward_observations",
    "intelligence_definition_from_protocol",
    "intelligence_evidence_snapshot",
    "load_ledger_evidence",
    "materialize_forward_tasks",
    "materialize_task_suite",
    "measure_genome_complexity",
    "operational_ignition_report",
    "pareto_dominates",
    "plugin_manifest",
    "propose_stall_fork",
    "record_campaign_ignition_trial",
    "run_loop1_campaign",
    "run_candidate_lifecycle",
    "select_minimized_candidate",
]
