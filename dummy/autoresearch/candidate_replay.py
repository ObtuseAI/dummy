"""Deterministic replay of real forecast genomes over frozen ledger inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from dummy.genome import ForecastGenome
from dummy.world_model.models import digest_json, thaw_json

from .ledger_pipeline import LedgerEvidenceRow, LedgerPartitionPlan
from .models import (
    AutoresearchValidationError,
    ComplexityProfile,
    EvaluationPartition,
    ResearchTask,
    TaskSuite,
)


def _gene_values(genome: ForecastGenome) -> dict[str, Any]:
    return {gene.name: thaw_json(gene.value) for gene in genome.genes}


def _number(values: dict[str, Any], name: str, default: float) -> float:
    try:
        return float(values.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True, slots=True)
class GenomeReplayPolicy:
    policy_id: str
    candidate_genome_id: str
    base_genome_id: str
    lineage_id: str
    market_anchor_weight: float
    base_market_anchor_weight: float
    abstention_threshold: float
    edge_threshold_cents: float
    max_entry_price_cents: int
    component_weight: float
    base_component_weight: float
    compute_units: float
    base_compute_units: float

    def __post_init__(self) -> None:
        if not self.lineage_id.strip():
            raise AutoresearchValidationError("replay lineage identity is required")
        if not 0.0 <= self.market_anchor_weight <= 1.0:
            raise AutoresearchValidationError("market anchor must be in [0, 1]")
        if not 0.0 <= self.base_market_anchor_weight < 1.0:
            raise AutoresearchValidationError("base market anchor must be in [0, 1)")
        if not 0.0 <= self.abstention_threshold <= 1.0:
            raise AutoresearchValidationError("abstention threshold must be in [0, 1]")
        if self.edge_threshold_cents < 0.0 or not 1 <= self.max_entry_price_cents <= 99:
            raise AutoresearchValidationError("decision thresholds are invalid")
        if not 0.0 <= self.component_weight <= 0.50:
            raise AutoresearchValidationError("component weight must be in [0, 0.5]")
        if not 0.0 <= self.base_component_weight <= 0.50:
            raise AutoresearchValidationError(
                "base component weight must be in [0, 0.5]"
            )
        if self.compute_units <= 0.0 or self.base_compute_units <= 0.0:
            raise AutoresearchValidationError("replay compute must be positive")
        if self.policy_id != digest_json(self.semantic_dict()):
            raise AutoresearchValidationError("genome replay policy ID mismatch")

    @classmethod
    def from_genomes(
        cls,
        *,
        candidate: ForecastGenome,
        base: ForecastGenome,
        lineage_id: str,
    ) -> GenomeReplayPolicy:
        if (
            candidate.vertical != base.vertical
            or candidate.market_type != base.market_type
            or candidate.horizon != base.horizon
        ):
            raise AutoresearchValidationError("candidate replay scope changed")
        candidate_values = _gene_values(candidate)
        base_values = _gene_values(base)
        anchor = _number(candidate_values, "synthesis.market_prior_weight", 0.5)
        base_anchor = _number(base_values, "synthesis.market_prior_weight", 0.5)
        abstention = _number(
            candidate_values,
            "abstention.epistemic_threshold",
            1.0,
        )
        edge = _number(candidate_values, "decision.edge_threshold_cents", 0.0)
        max_entry = round(
            _number(candidate_values, "execution.max_entry_price_cents", 99.0)
        )
        component_weight = _number(candidate_values, "synthesis.component_weight", 0.0)
        base_component_weight = _number(base_values, "synthesis.component_weight", 0.0)

        def compute(values: dict[str, Any]) -> float:
            replay_depth = _number(values, "replay.depth", 0.0)
            simulation_budget = _number(values, "simulation.path_budget", 0.0)
            return round(1.0 + 0.01 * replay_depth + simulation_budget / 10_000.0, 12)

        semantic = {
            "schema_version": 1,
            "candidate_genome_id": candidate.genome_id,
            "base_genome_id": base.genome_id,
            "lineage_id": lineage_id,
            "market_anchor_weight": anchor,
            "base_market_anchor_weight": base_anchor,
            "abstention_threshold": abstention,
            "edge_threshold_cents": edge,
            "max_entry_price_cents": max_entry,
            "component_weight": component_weight,
            "base_component_weight": base_component_weight,
            "compute_units": compute(candidate_values),
            "base_compute_units": compute(base_values),
            "transformation": "hold_non_market_component_fixed_and_change_anchor_v1",
            "execution_authority": False,
        }
        return cls(
            policy_id=digest_json(semantic),
            candidate_genome_id=candidate.genome_id,
            base_genome_id=base.genome_id,
            lineage_id=lineage_id,
            market_anchor_weight=anchor,
            base_market_anchor_weight=base_anchor,
            abstention_threshold=abstention,
            edge_threshold_cents=edge,
            max_entry_price_cents=max_entry,
            component_weight=component_weight,
            base_component_weight=base_component_weight,
            compute_units=compute(candidate_values),
            base_compute_units=compute(base_values),
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "candidate_genome_id": self.candidate_genome_id,
            "base_genome_id": self.base_genome_id,
            "lineage_id": self.lineage_id,
            "market_anchor_weight": self.market_anchor_weight,
            "base_market_anchor_weight": self.base_market_anchor_weight,
            "abstention_threshold": self.abstention_threshold,
            "edge_threshold_cents": self.edge_threshold_cents,
            "max_entry_price_cents": self.max_entry_price_cents,
            "component_weight": self.component_weight,
            "base_component_weight": self.base_component_weight,
            "compute_units": self.compute_units,
            "base_compute_units": self.base_compute_units,
            "transformation": "hold_non_market_component_fixed_and_change_anchor_v1",
            "execution_authority": False,
        }

    def probability(self, row: LedgerEvidenceRow) -> float:
        base_non_market = 1.0 - self.base_market_anchor_weight
        candidate_non_market = 1.0 - self.market_anchor_weight
        scale = candidate_non_market / base_non_market
        adjusted = row.market_prior_probability + scale * (
            row.incumbent_probability - row.market_prior_probability
        )
        if row.component_probability is not None:
            adjusted = (
                1.0 - self.component_weight
            ) * adjusted + self.component_weight * row.component_probability
        return min(0.999, max(0.001, adjusted))

    def decision(self, row: LedgerEvidenceRow) -> tuple[float | None, str | None]:
        candidate = self.probability(row)
        if row.forecast_uncertainty > self.abstention_threshold:
            return None, "uncertainty_threshold"
        edge = candidate - row.market_prior_probability
        if abs(edge) * 100.0 < self.edge_threshold_cents:
            return None, "edge_threshold"
        entry_price = round(
            100.0
            * (
                row.market_prior_probability
                if edge > 0.0
                else 1.0 - row.market_prior_probability
            )
        )
        if entry_price > self.max_entry_price_cents:
            return None, "entry_price_threshold"
        return candidate, None


def measure_genome_complexity(
    base: ForecastGenome,
    candidate: ForecastGenome,
) -> ComplexityProfile:
    base_values = _gene_values(base)
    candidate_values = _gene_values(candidate)
    names = set(base_values) | set(candidate_values)
    changed = {
        name for name in names if base_values.get(name) != candidate_values.get(name)
    }
    added = set(candidate_values) - set(base_values)
    branch_genes = {
        "decision.edge_threshold_cents",
        "execution.max_entry_price_cents",
        "synthesis.component_weight",
    }
    new_branches = len(added & branch_genes)
    base_simulation = _number(base_values, "simulation.path_budget", 0.0)
    candidate_simulation = _number(candidate_values, "simulation.path_budget", 0.0)
    replay_delta = max(0.0, candidate_simulation - base_simulation) / 10_000.0
    return ComplexityProfile(
        changed_modules=1 if changed else 0,
        cyclomatic_delta=new_branches,
        new_branches=new_branches,
        new_configuration_values=len(changed),
        state_space_growth=len(added),
        added_dependencies=0,
        new_artifact_schemas=0,
        replay_cost_delta=replay_delta,
        explanation_complexity=len(changed),
        dead_code_items=0,
        test_surface_expansion=max(1, len(changed)),
    )


def _replayed_order_terms(
    row: LedgerEvidenceRow,
    candidate: float | None,
) -> tuple[str, str, int] | None:
    """Return the candidate order that can be compared with recorded execution.

    Candidate replay does not mutate sizing, so an actionable replay preserves
    the recorded positive contract count.  Direction alone is not execution
    identity: the recorded fill can be inherited only when the action, side,
    entry price, and count all match.
    """
    if candidate is None:
        return None
    if row.count <= 0:
        return None
    edge = candidate - row.market_prior_probability
    candidate_action = "BUY_YES" if edge > 0.0 else "BUY_NO"
    candidate_side = "yes" if edge > 0.0 else "no"
    candidate_price = round(
        100.0
        * (
            row.market_prior_probability
            if edge > 0.0
            else 1.0 - row.market_prior_probability
        )
    )
    return candidate_action, candidate_side, candidate_price


def _exact_recorded_decision(
    row: LedgerEvidenceRow,
    candidate: float | None,
) -> bool:
    replayed = _replayed_order_terms(row, candidate)
    if replayed is None:
        return False
    candidate_action, candidate_side, candidate_price = replayed
    return (
        row.action == candidate_action
        and row.side.lower() == candidate_side
        and row.price_cents == candidate_price
    )


def replay_task(
    row: LedgerEvidenceRow,
    *,
    partition: EvaluationPartition,
    policy: GenomeReplayPolicy,
) -> ResearchTask:
    candidate, abstain_reason = policy.decision(row)
    candidate_abstained = candidate is None
    exact_recorded_decision = _exact_recorded_decision(row, candidate)
    witnessed_settled_fill = row.fill_count > 0 and row.settled_pnl_cents is not None
    candidate_fill_verified = (
        exact_recorded_decision
        and witnessed_settled_fill
        and 0 < row.fill_count <= row.count
    )
    incumbent_fill_verified = witnessed_settled_fill
    outcome = float(row.result_yes)
    abstention_was_correct = (row.incumbent_probability - outcome) ** 2 > (
        row.market_prior_probability - outcome
    ) ** 2
    replay_payload = {
        "policy_id": policy.policy_id,
        "evidence_input_digest": row.input_digest,
        "candidate_probability": candidate,
        "abstain_reason": abstain_reason,
    }
    replay_digest = digest_json(replay_payload)
    candidate_cost = policy.compute_units
    base_cost = policy.base_compute_units
    return ResearchTask(
        case_id=digest_json(
            {
                "candidate_genome_id": policy.candidate_genome_id,
                "evidence_row_id": row.evidence_row_id,
            }
        ),
        partition=partition,
        event_cluster_id=row.event_cluster_id,
        selection_keys=(f"market:{row.market_ticker}",),
        decision_at=row.decision_at,
        market_close_at=row.settlement_received_at,
        settlement_received_at=row.settlement_received_at,
        candidate_probability=candidate,
        incumbent_probability=row.incumbent_probability,
        market_prior_probability=row.market_prior_probability,
        result_yes=row.result_yes,
        transfer_group=row.market_regime,
        regime=f"{row.cohort_scope}|{row.market_regime}",
        evidence_ids=(row.evidence_row_id,),
        candidate_abstained=candidate_abstained,
        abstention_was_correct=abstention_was_correct,
        forced_coverage=row.forced_coverage,
        point_in_time_verified=True,
        settlement_verified=True,
        evidence_reality="VERIFIED_SETTLEMENT",
        source_family_ids=row.source_family_ids,
        candidate_compute_units=candidate_cost,
        incumbent_compute_units=base_cost,
        candidate_cost_microunits=candidate_cost,
        incumbent_cost_microunits=base_cost,
        candidate_fill_verified=candidate_fill_verified,
        incumbent_fill_verified=incumbent_fill_verified,
        candidate_claimed_fill_performance=candidate_fill_verified,
        candidate_pnl_cents=(
            int(row.settled_pnl_cents) if candidate_fill_verified else 0
        ),
        incumbent_pnl_cents=(
            int(row.settled_pnl_cents) if incumbent_fill_verified else 0
        ),
        candidate_counterfactual_pnl_cents=0,
        replay_digest=replay_digest,
        repeated_replay_digest=digest_json(replay_payload),
        candidate_used_future_evidence=False,
        candidate_marked_promotion_eligible=False,
        candidate_claimed_contested=(
            candidate is not None
            and abs(candidate - row.market_prior_probability) >= 0.05
        ),
        claimed_independent_units=1,
        book_valid=0.0 < row.market_prior_probability < 1.0,
        candidate_used_book=True,
        lineup_received_at=None,
        candidate_used_lineup=False,
        close_time_provenance="SETTLEMENT_RECEIPT_UPPER_BOUND",
    )


def materialize_task_suite(
    rows: Iterable[LedgerEvidenceRow],
    *,
    plan: LedgerPartitionPlan,
    policy: GenomeReplayPolicy,
) -> TaskSuite:
    tasks = tuple(
        replay_task(row, partition=partition, policy=policy)
        for row in rows
        if (partition := plan.partition_for(row.evidence_row_id)) is not None
    )
    return TaskSuite.create(tasks)


def materialize_forward_tasks(
    rows: Iterable[LedgerEvidenceRow],
    *,
    policy: GenomeReplayPolicy,
) -> tuple[ResearchTask, ...]:
    return tuple(
        replay_task(
            row,
            partition=EvaluationPartition.EXTERNAL_GENERALIZATION,
            policy=policy,
        )
        for row in rows
    )


__all__ = [
    "GenomeReplayPolicy",
    "materialize_forward_tasks",
    "materialize_task_suite",
    "measure_genome_complexity",
    "replay_task",
]
