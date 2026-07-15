from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest

from dummy.evolution import (
    CandidateEvaluationInput,
    EvolutionArchive,
    EvolutionEvaluationCase,
    build_population,
    evaluate_evolution_family,
    promotion_proposal,
    rollback_proposal,
)
from dummy.genome import (
    ForecastGenome,
    Gene,
    GeneCategory,
    GenomeValidationError,
    MutationLevel,
    MutationOperation,
    MutationOperator,
    propose_mutation,
)


NOW = datetime(2026, 7, 15, 2, 0, tzinfo=timezone.utc)


def _base() -> ForecastGenome:
    return ForecastGenome.create(
        label="evolution baseline",
        vertical="CRYPTO",
        market_type="BTC_15M",
        horizon="15m",
        generation=0,
        parent_genome_ids=(),
        genes=(
            Gene(
                name="market.anchor",
                category=GeneCategory.MARKET_PRIOR_WEIGHT,
                value=0.5,
                version="v1",
                evidence_ids=("training-evidence",),
            ),
        ),
        created_at=NOW,
        evidence_ids=("training-evidence",),
    )


def _proposal(value: float = 0.6):
    base = _base()
    return propose_mutation(
        base,
        level=MutationLevel.PARAMETERS,
        operations=(
            MutationOperation(
                operator=MutationOperator.SET,
                gene_name="market.anchor",
                category=GeneCategory.MARKET_PRIOR_WEIGHT,
                value=value,
                gene_version=f"v-{value}",
                rationale="held-out candidate hypothesis",
            ),
        ),
        target_paths=(f"dummy/genome/candidates/{value}.json",),
        created_at=NOW,
        evidence_ids=(f"selection-{value}",),
    )


def _cases(
    *,
    clusters: int = 20,
    candidate_good: bool = True,
    duplicate_rows: bool = False,
) -> tuple[EvolutionEvaluationCase, ...]:
    cases = []
    for index in range(clusters):
        result = index % 2 == 0
        candidate = (0.9 if result else 0.1) if candidate_good else 0.5
        incumbent = 0.1 if result else 0.9
        repeats = 2 if duplicate_rows else 1
        for repeat in range(repeats):
            decision = NOW + timedelta(days=index, seconds=repeat)
            cases.append(
                EvolutionEvaluationCase(
                    case_id=f"case-{index:03d}-{repeat}",
                    event_cluster_id=f"heldout-{index:03d}",
                    decision_at=decision,
                    market_close_at=decision + timedelta(minutes=15),
                    settlement_received_at=decision + timedelta(minutes=20),
                    candidate_probability=candidate,
                    incumbent_probability=incumbent,
                    market_prior_probability=0.5,
                    result_yes=result,
                    transfer_group="primary" if index < clusters // 2 else "transfer",
                    regime="normal" if index < clusters // 2 else "shifted",
                    settlement_verified=True,
                    point_in_time_verified=True,
                    evidence_ids=(f"settlement-{index:03d}-{repeat}",),
                )
            )
    return tuple(cases)


def _input(
    *,
    value: float = 0.6,
    cases: tuple[EvolutionEvaluationCase, ...] | None = None,
) -> CandidateEvaluationInput:
    proposal = _proposal(value)
    assert proposal.candidate_genome is not None
    return CandidateEvaluationInput(
        candidate=proposal.candidate_genome,
        mutation_proposal=proposal,
        incumbent_id="incumbent-v1",
        market_prior_id="market-price-v1",
        primary_transfer_group="primary",
        training_event_cluster_ids=("training-cluster",),
        candidate_selection_evidence_ids=(f"selection-{value}",),
        held_out_cases=cases or _cases(),
        deterministic_replay_verified=True,
        replay_report_id=f"replay-{value}",
        governance_preserved=True,
        governance_report_id=f"governance-{value}",
    )


def test_empty_evolution_evidence_is_honest() -> None:
    report = evaluate_evolution_family(())
    assert report["status"] == "INSUFFICIENT_SETTLED_EVIDENCE"
    assert report["candidate_count"] == 0
    assert report["automatic_promotion"] is False


def test_training_or_selection_leakage_is_rejected_before_evaluation() -> None:
    clean = _input()
    with pytest.raises(GenomeValidationError, match="held-out event cluster"):
        replace(
            clean,
            training_event_cluster_ids=(clean.held_out_cases[0].event_cluster_id,),
        )
    with pytest.raises(GenomeValidationError, match="held-out evidence"):
        replace(
            clean,
            candidate_selection_evidence_ids=(clean.held_out_cases[0].evidence_ids[0],),
        )


def test_supported_synthetic_case_survives_cluster_transfer_and_correction() -> None:
    report = evaluate_evolution_family(
        (_input(),),
        minimum_clusters=20,
        minimum_transfer_clusters=10,
        bootstrap_simulations=1_000,
        permutation_draws=1_000,
    )
    candidate = report["candidate_reports"][0]
    assert report["status"] == "EVALUATED"
    assert candidate["verdict"] == "HELD_OUT_IMPROVEMENT_SUPPORTED"
    assert candidate["clustered_gain_vs_incumbent"]["positive_interval"] is True
    assert candidate["transfer_passed"] is True
    assert candidate["multiple_testing"]["rejected_null"] is True
    assert candidate["eligible_for_promotion"] is False
    proposal = promotion_proposal(report, candidate_id=candidate["candidate_id"])
    assert proposal["status"] == "READY_FOR_EXPLICIT_HUMAN_REVIEW"
    assert proposal["eligible_for_promotion"] is False
    assert proposal["applied"] is False


def test_duplicate_rows_do_not_inflate_event_cluster_gate() -> None:
    report = evaluate_evolution_family(
        (_input(cases=_cases(clusters=10, duplicate_rows=True)),),
        minimum_clusters=20,
        minimum_transfer_clusters=5,
        bootstrap_simulations=1_000,
        permutation_draws=1_000,
    )
    candidate = report["candidate_reports"][0]
    assert candidate["held_out_case_count"] == 20
    assert candidate["held_out_event_cluster_count"] == 10
    assert candidate["verdict"] == "INSUFFICIENT_SETTLED_EVIDENCE"


def test_transfer_failure_blocks_claim_even_when_primary_gain_is_positive() -> None:
    cases = tuple(
        replace(case, transfer_group="primary") for case in _cases()
    )
    report = evaluate_evolution_family(
        (_input(cases=cases),),
        minimum_clusters=20,
        minimum_transfer_clusters=10,
        bootstrap_simulations=1_000,
        permutation_draws=1_000,
    )
    candidate = report["candidate_reports"][0]
    assert candidate["transfer_passed"] is False
    assert candidate["verdict"] == "INSUFFICIENT_EDGE_EVIDENCE"


def test_family_correction_archive_population_and_rollback_are_deterministic() -> None:
    first, second = _input(value=0.6), _input(value=0.7)
    report = evaluate_evolution_family(
        (first, second),
        minimum_clusters=20,
        minimum_transfer_clusters=10,
        bootstrap_simulations=1_000,
        permutation_draws=1_000,
    )
    assert len(report["candidate_reports"]) == 2
    assert all(
        item["multiple_testing"]["method"] == "HOLM_BONFERRONI"
        for item in report["candidate_reports"]
    )
    archive = EvolutionArchive()
    assert archive.append(report) == report["family_report_id"]
    assert archive.append(report) == report["family_report_id"]
    assert archive.snapshot()["report_count"] == 1
    population = build_population(
        (first.mutation_proposal, second.mutation_proposal),
        maximum_size=2,
    )
    assert len(population.genomes) == 2
    rollback = rollback_proposal(
        current_genome_id=second.candidate.genome_id,
        target_genome_id=first.candidate.genome_id,
        trigger="transfer_regression",
        last_healthy_fitness_id=report["fitness_records"][0]["fitness_id"],
        evidence_ids=(report["family_report_id"],),
        decided_at=NOW,
    )
    assert rollback["authority_direction"] == "CONTRACTION_ONLY"
    assert rollback["applied"] is False


def test_phase6_audit_is_deterministic_and_empty_claim_safe(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "scripts" / "run_vnext_phase6_audit.py"
    command = [sys.executable, str(script), "--output-dir", str(tmp_path)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    first = {
        path.name: path.read_bytes() for path in sorted(tmp_path.glob("*.json"))
    }
    subprocess.run(command, check=True, capture_output=True, text=True)
    second = {
        path.name: path.read_bytes() for path in sorted(tmp_path.glob("*.json"))
    }
    assert first == second
    evidence = json.loads(first["VNEXT_PHASE6_EVOLUTION_EVIDENCE.json"])
    policy = json.loads(first["VNEXT_PHASE6_EVOLUTION_POLICY.json"])
    assert evidence["status"] == "INSUFFICIENT_SETTLED_EVIDENCE"
    assert policy["mutation"]["automatic_promotion"] is False
    assert policy["evaluation"]["multiple_testing"] == "HOLM_BONFERRONI"
