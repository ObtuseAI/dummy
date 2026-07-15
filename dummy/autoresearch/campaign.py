"""Bounded Loop-1 lineage campaign over genuine point-in-time ledger evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dummy.genome import (
    ForecastGenome,
    GeneCategory,
    MutationLevel,
    MutationOperation,
    MutationOperator,
    propose_mutation,
)
from dummy.world_model.models import digest_json

from .candidate_minimizer import select_minimized_candidate
from .candidate_replay import (
    GenomeReplayPolicy,
    materialize_task_suite,
    measure_genome_complexity,
)
from .complexity_gate import complexity_score
from .external_evaluator import evaluate_external_generalization
from .ledger_pipeline import LedgerEvidenceRow, LedgerPartitionPlan
from .lineage_bandit import LineageState, allocate_lineage
from .models import EvaluationPartition, PrivateEvaluationReceipt, ResearchPolicy, iso
from .outer_researcher import (
    OuterEvolutionResearcher,
    ResearchBudget,
    ResearchExperiment,
)
from .private_evaluator import evaluate_private_selection
from .public_evaluator import evaluate_visible_development


LOOP1_LINEAGES = (
    "abstention-first",
    "calibration-first",
    "crypto-liquidity",
    "execution-aware",
    "market-prior-anchored",
)


@dataclass(frozen=True, slots=True)
class CandidateRecipe:
    lineage_id: str
    level: MutationLevel
    operations: tuple[MutationOperation, ...]
    behavioral_intent: str


def _set(
    name: str,
    category: GeneCategory,
    value: float | int,
    *,
    rationale: str,
) -> MutationOperation:
    return MutationOperation(
        operator=MutationOperator.SET,
        gene_name=name,
        category=category,
        value=value,
        gene_version="autoresearch-loop1-v1",
        rationale=rationale,
    )


def _add(
    name: str,
    value: float | int,
    *,
    rationale: str,
) -> MutationOperation:
    return MutationOperation(
        operator=MutationOperator.ADD,
        gene_name=name,
        category=GeneCategory.DECISION_RULE,
        value=value,
        gene_version="autoresearch-loop1-v1",
        rationale=rationale,
    )


def loop1_recipes() -> dict[str, CandidateRecipe]:
    return {
        "market-prior-anchored": CandidateRecipe(
            lineage_id="market-prior-anchored",
            level=MutationLevel.PARAMETERS,
            operations=(
                _set(
                    "synthesis.market_prior_weight",
                    GeneCategory.MARKET_PRIOR_WEIGHT,
                    0.60,
                    rationale="test stronger market anchoring under hidden settlement truth",
                ),
            ),
            behavioral_intent="shrink the non-market component by twenty percent",
        ),
        "calibration-first": CandidateRecipe(
            lineage_id="calibration-first",
            level=MutationLevel.PARAMETERS,
            operations=(
                _set(
                    "synthesis.market_prior_weight",
                    GeneCategory.MARKET_PRIOR_WEIGHT,
                    0.55,
                    rationale="test mild probability shrinkage",
                ),
                _set(
                    "abstention.epistemic_threshold",
                    GeneCategory.ABSTENTION_THRESHOLD,
                    0.35,
                    rationale="reject legacy high-uncertainty forecasts",
                ),
            ),
            behavioral_intent="combine mild shrinkage with an uncertainty boundary",
        ),
        "abstention-first": CandidateRecipe(
            lineage_id="abstention-first",
            level=MutationLevel.PARAMETERS,
            operations=(
                _set(
                    "abstention.epistemic_threshold",
                    GeneCategory.ABSTENTION_THRESHOLD,
                    0.12,
                    rationale="test a narrow epistemic coverage boundary",
                ),
            ),
            behavioral_intent="abstain when recorded epistemic uncertainty exceeds 0.12",
        ),
        "crypto-liquidity": CandidateRecipe(
            lineage_id="crypto-liquidity",
            level=MutationLevel.FORECAST_STRATEGY,
            operations=(
                _add(
                    "decision.edge_threshold_cents",
                    7,
                    rationale="require a decision-time edge buffer",
                ),
                _add(
                    "execution.max_entry_price_cents",
                    75,
                    rationale="avoid expensive binary entries in replay",
                ),
            ),
            behavioral_intent="require seven cents of edge and cap entry price at 75",
        ),
        "execution-aware": CandidateRecipe(
            lineage_id="execution-aware",
            level=MutationLevel.FORECAST_STRATEGY,
            operations=(
                _add(
                    "decision.edge_threshold_cents",
                    9,
                    rationale="require a wider cost and slippage buffer",
                ),
                _add(
                    "execution.max_entry_price_cents",
                    65,
                    rationale="bound entry exposure without using future fills",
                ),
            ),
            behavioral_intent="require nine cents of edge and cap entry price at 65",
        ),
    }


@dataclass(frozen=True, slots=True)
class CampaignCandidateResult:
    experiment_id: str
    lineage_id: str
    candidate_genome: ForecastGenome
    private_receipt: PrivateEvaluationReceipt
    public_evaluation_id: str
    public_fitness: float
    external_evaluation: dict[str, Any] | None
    minimization: dict[str, Any] | None
    complexity_score: float
    compute_units_used: float
    private_selected: bool
    external_passed: bool
    forward_paper_eligible: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "lineage_id": self.lineage_id,
            "candidate_genome": self.candidate_genome.to_dict(),
            "private_receipt": self.private_receipt.to_dict(),
            "public_evaluation_id": self.public_evaluation_id,
            "public_fitness": round(self.public_fitness, 12),
            "external_evaluation": self.external_evaluation,
            "minimization": self.minimization,
            "complexity_score": round(self.complexity_score, 12),
            "compute_units_used": round(self.compute_units_used, 12),
            "private_selected": self.private_selected,
            "external_passed": self.external_passed,
            "forward_paper_eligible": self.forward_paper_eligible,
            "private_item_details": None,
            "source_edit_applied": False,
            "runtime_application": False,
            "automatic_promotion": False,
            "execution_authority": False,
        }


def _evaluate_candidate(
    *,
    experiment: ResearchExperiment,
    lineage_id: str,
    candidate: ForecastGenome,
    base: ForecastGenome,
    rows: tuple[LedgerEvidenceRow, ...],
    plan: LedgerPartitionPlan,
    recipe: CandidateRecipe,
    created_at: datetime,
) -> tuple[CampaignCandidateResult, PrivateEvaluationReceipt]:
    policy = GenomeReplayPolicy.from_genomes(
        candidate=candidate,
        base=base,
        lineage_id=lineage_id,
    )
    suite = materialize_task_suite(rows, plan=plan, policy=policy)
    complexity = measure_genome_complexity(base, candidate)
    public = evaluate_visible_development(
        candidate.genome_id,
        suite.partition(EvaluationPartition.VISIBLE_DEVELOPMENT),
        complexity_profile=complexity,
    )
    if not public.accepted:
        raise ValueError("candidate failed visible mechanical replay")
    private, receipt = evaluate_private_selection(
        candidate.genome_id,
        suite.partition(EvaluationPartition.PRIVATE_SELECTION),
        complexity_profile=complexity,
    )
    selected_candidate = candidate
    selected_policy = policy
    selected_private = private
    selected_receipt = receipt
    selected_complexity = complexity
    minimization_dict: dict[str, Any] | None = None

    if private.accepted and len(recipe.operations) > 1:
        minimized_proposals = []
        for removed_index in range(len(recipe.operations)):
            operations = tuple(
                operation
                for index, operation in enumerate(recipe.operations)
                if index != removed_index
            )
            proposal = propose_mutation(
                base,
                level=recipe.level,
                operations=operations,
                target_paths=(f"dummy/forecasting/research/{lineage_id}-minimized.json",),
                created_at=created_at,
                evidence_ids=(plan.evidence_fingerprint, "semantic-distillation-v1"),
            )
            if proposal.candidate_genome is None:
                continue
            minimized = proposal.candidate_genome
            minimized_policy = GenomeReplayPolicy.from_genomes(
                candidate=minimized,
                base=base,
                lineage_id=lineage_id,
            )
            minimized_suite = materialize_task_suite(
                rows,
                plan=plan,
                policy=minimized_policy,
            )
            minimized_complexity = measure_genome_complexity(base, minimized)
            minimized_private, minimized_receipt = evaluate_private_selection(
                minimized.genome_id,
                minimized_suite.partition(EvaluationPartition.PRIVATE_SELECTION),
                complexity_profile=minimized_complexity,
            )
            decision = select_minimized_candidate(
                private,
                minimized_private,
                original_complexity=complexity,
                minimized_complexity=minimized_complexity,
                behavioral_spec={
                    "lineage_id": lineage_id,
                    "scope": plan.scope,
                    "intent": recipe.behavioral_intent,
                    "removed_operation_index": removed_index,
                    "inputs": "frozen_earliest_decision_ledger_rows",
                    "output": "probability_or_abstention",
                },
            )
            minimized_proposals.append(
                (
                    decision,
                    minimized,
                    minimized_policy,
                    minimized_private,
                    minimized_receipt,
                    minimized_complexity,
                )
            )
        retained = [item for item in minimized_proposals if item[0].retained_minimized]
        if retained:
            chosen = max(retained, key=lambda item: item[3].fitness)
            (
                decision,
                selected_candidate,
                selected_policy,
                selected_private,
                selected_receipt,
                selected_complexity,
            ) = chosen
            minimization_dict = decision.to_dict()
        elif minimized_proposals:
            minimization_dict = minimized_proposals[0][0].to_dict()

    selected_suite = materialize_task_suite(
        rows,
        plan=plan,
        policy=selected_policy,
    )
    selected_public = evaluate_visible_development(
        selected_candidate.genome_id,
        selected_suite.partition(EvaluationPartition.VISIBLE_DEVELOPMENT),
        complexity_profile=selected_complexity,
    )
    external = None
    if selected_private.accepted:
        external = evaluate_external_generalization(
            selected_candidate.genome_id,
            selected_suite.partition(EvaluationPartition.EXTERNAL_GENERALIZATION),
            complexity_profile=selected_complexity,
        )
    external_passed = bool(external and external.accepted)
    compute_used = selected_policy.compute_units * len(selected_suite.tasks)
    result = CampaignCandidateResult(
        experiment_id=experiment.experiment_id,
        lineage_id=lineage_id,
        candidate_genome=selected_candidate,
        private_receipt=selected_receipt,
        public_evaluation_id=selected_public.evaluation_id,
        public_fitness=selected_public.fitness,
        external_evaluation=external.to_dict() if external else None,
        minimization=minimization_dict,
        complexity_score=complexity_score(selected_complexity),
        compute_units_used=compute_used,
        private_selected=selected_private.accepted,
        external_passed=external_passed,
        forward_paper_eligible=selected_private.accepted and external_passed,
    )
    return result, selected_receipt


def run_loop1_campaign(
    *,
    rows: tuple[LedgerEvidenceRow, ...],
    plan: LedgerPartitionPlan,
    base_genome: ForecastGenome,
    created_at: datetime,
    maximum_experiments: int = 5,
    per_experiment_compute_budget: float = 500.0,
) -> dict[str, Any]:
    recipes = loop1_recipes()
    if maximum_experiments != len(LOOP1_LINEAGES):
        raise ValueError("Loop-1 v1 requires one bounded trial per eligible lineage")
    policy = ResearchPolicy.create(
        label="Dummy Loop-1 manual outer researcher",
        strategy="lineage_ucb_greedy_within_lineage_fixed_first_pass",
        lineage_ids=LOOP1_LINEAGES,
    )
    researcher = OuterEvolutionResearcher(policy)
    states = tuple(
        LineageState(
            lineage_id=lineage_id,
            strategy=lineage_id,
            champion_candidate_id=base_genome.genome_id,
        )
        for lineage_id in LOOP1_LINEAGES
    )
    results: list[CampaignCandidateResult] = []
    allocations: list[dict[str, Any]] = []
    for _ in range(maximum_experiments):
        allocation = allocate_lineage(states)
        lineage_id = allocation.selected_lineage_id
        recipe = recipes[lineage_id]
        experiment = researcher.propose_experiment(
            lineage_states=states,
            base_genome=base_genome,
            level=recipe.level,
            operations=recipe.operations,
            target_paths=(f"dummy/forecasting/research/{lineage_id}.json",),
            created_at=created_at,
            evidence_ids=(plan.evidence_fingerprint, f"lineage:{lineage_id}"),
            budget=ResearchBudget(
                maximum_experiments=maximum_experiments,
                maximum_compute_units=per_experiment_compute_budget,
                maximum_cost_microunits=per_experiment_compute_budget,
                maximum_wall_seconds=300,
            ),
        )
        candidate = experiment.mutation_proposal.candidate_genome
        if candidate is None:
            raise ValueError("constitutional Loop-1 recipe was unexpectedly blocked")
        result, receipt = _evaluate_candidate(
            experiment=experiment,
            lineage_id=lineage_id,
            candidate=candidate,
            base=base_genome,
            rows=rows,
            plan=plan,
            recipe=recipe,
            created_at=created_at,
        )
        if result.compute_units_used > per_experiment_compute_budget:
            raise ValueError("candidate exceeded its fixed compute budget")
        results.append(result)
        allocations.append(allocation.to_dict())
        states = tuple(
            researcher.ingest_private_receipt(state, receipt)
            if state.lineage_id == lineage_id
            else state
            for state in states
        )

    cutoff = max(row.settlement_received_at for row in rows)
    candidates = [result.to_dict() for result in results]
    eligible = [result for result in results if result.forward_paper_eligible]
    best = (
        max(eligible, key=lambda item: item.private_receipt.fitness)
        if eligible
        else None
    )
    body: dict[str, Any] = {
        "schema_version": 1,
        "campaign_name": "DUMMY_AUTORESEARCH_LOOP1_REAL_LEDGER_V1",
        "created_at": iso(created_at),
        "evidence_cutoff": iso(cutoff),
        "base_genome_id": base_genome.genome_id,
        "scope": plan.scope,
        "partition_plan": plan.public_manifest(),
        "budget": {
            "maximum_experiments": maximum_experiments,
            "experiments_completed": len(results),
            "per_experiment_compute_units": per_experiment_compute_budget,
            "total_compute_units_used": round(
                sum(result.compute_units_used for result in results), 12
            ),
            "same_model_access": True,
            "same_private_evaluator": True,
            "same_starting_genome": True,
        },
        "allocations": allocations,
        "candidates": candidates,
        "genuine_private_candidate_trials": len(results),
        "genuine_external_generalization_trials": sum(
            result.external_evaluation is not None for result in results
        ),
        "private_survivors": sum(result.private_selected for result in results),
        "external_survivors": len(eligible),
        "best_forward_candidate_id": (
            best.candidate_genome.genome_id if best else None
        ),
        "unavailable_lineages": [
            {
                "lineage_id": "mlb-simulation",
                "status": "UNAVAILABLE_MISSING_POINT_IN_TIME_COMPONENT_OUTPUTS",
                "reason": (
                    "authoritative decision rows do not preserve the MLB PA-simulator "
                    "component output across three chronological partitions"
                ),
                "outcome_rows_used_to_reconstruct_component": False,
                "experiment_run": False,
            }
        ],
        "private_item_details_exposed": False,
        "performance_claim_supported": False,
        "forward_paper_required": bool(eligible),
        "source_edits_applied": False,
        "runtime_application": False,
        "automatic_promotion": False,
        "execution_authority": False,
        "capital_authority": False,
    }
    body["campaign_id"] = digest_json(body)
    return body


def write_campaign_report(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


__all__ = [
    "LOOP1_LINEAGES",
    "CandidateRecipe",
    "loop1_recipes",
    "run_loop1_campaign",
    "write_campaign_report",
]
