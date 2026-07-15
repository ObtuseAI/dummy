from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from dummy.autoresearch import (
    AutoresearchValidationError,
    ComplexityProfile,
    EvaluationPartition,
    ExperimentLedger,
    IgnitionLevel,
    IgnitionTrial,
    LineageState,
    OuterEvolutionResearcher,
    ResearchBudget,
    ResearchPolicy,
    ResearchRole,
    ResearchTask,
    TaskSuite,
    allocate_lineage,
    audit_reward_hacking,
    build_task_suite,
    distill_context,
    evaluate_ignition,
    evaluate_private_selection,
    propose_stall_fork,
    run_candidate_lifecycle,
    select_minimized_candidate,
)
from dummy.constitution import protected_manifest_dict
from dummy.genome import (
    GeneCategory,
    MutationLevel,
    MutationOperation,
    MutationOperator,
    pilot_genomes,
)


NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def _task(
    partition: EvaluationPartition,
    index: int,
    **overrides: object,
) -> ResearchTask:
    result = index % 2 == 0
    prefix = partition.value.lower()
    partition_offset = {
        EvaluationPartition.VISIBLE_DEVELOPMENT: 0,
        EvaluationPartition.PRIVATE_SELECTION: 100,
        EvaluationPartition.EXTERNAL_GENERALIZATION: 200,
    }[partition]
    day = index + partition_offset
    data: dict[str, object] = {
        "case_id": f"{prefix}-case-{index}",
        "partition": partition,
        "event_cluster_id": f"{prefix}-cluster-{index}",
        "selection_keys": (f"{prefix}-date-{index}", f"{prefix}-symbol-{index}"),
        "decision_at": NOW + timedelta(days=day),
        "market_close_at": NOW + timedelta(days=day, minutes=15),
        "settlement_received_at": NOW + timedelta(days=day, minutes=20),
        "candidate_probability": 0.8 if result else 0.2,
        "incumbent_probability": 0.6 if result else 0.4,
        "market_prior_probability": 0.5,
        "result_yes": result,
        "transfer_group": "primary" if index < 2 else "transfer",
        "regime": "normal" if index < 2 else "shifted",
        "evidence_ids": (f"{prefix}-settlement-{index}",),
    }
    data.update(overrides)
    return ResearchTask(**data)  # type: ignore[arg-type]


def _suite() -> TaskSuite:
    return build_task_suite(
        tuple(
            _task(partition, index)
            for partition in EvaluationPartition
            for index in range(4)
        )
    )


def test_task_suite_enforces_three_disjoint_hidden_partitions() -> None:
    suite = _suite()
    assert suite.partition_manifest()["PRIVATE_SELECTION"][
        "item_details_exposed_to_outer_loop"
    ] is False
    visible = _task(EvaluationPartition.VISIBLE_DEVELOPMENT, 10)
    private = replace(
        _task(EvaluationPartition.PRIVATE_SELECTION, 10),
        event_cluster_id=visible.event_cluster_id,
    )
    external = _task(EvaluationPartition.EXTERNAL_GENERALIZATION, 10)
    with pytest.raises(AutoresearchValidationError, match="crosses"):
        TaskSuite.create((visible, private, external))


def test_private_evaluator_returns_aggregate_receipt_and_lifecycle() -> None:
    suite = _suite()
    summary, receipt = evaluate_private_selection(
        "candidate-alpha",
        suite.partition(EvaluationPartition.PRIVATE_SELECTION),
    )
    assert summary.accepted is True
    assert summary.item_feedback == ()
    assert receipt.accepted is True
    assert receipt.to_dict()["item_details"] is None
    assert "case" not in json.dumps(receipt.to_dict()).lower()

    lifecycle = run_candidate_lifecycle(
        "candidate-alpha",
        suite,
        constitution_allowed=True,
    )
    assert lifecycle.survived_private_selection is True
    assert lifecycle.forward_paper_required is True
    assert lifecycle.external_evaluation is not None
    assert lifecycle.external_evaluation.selection_eligible is False
    assert lifecycle.human_promotion_required is True


def test_reward_hacking_canaries_detect_all_eight_failure_modes() -> None:
    task = _task(
        EvaluationPartition.PRIVATE_SELECTION,
        0,
        candidate_probability=0.52,
        source_family_ids=("same-family", "same-family"),
        candidate_used_future_evidence=True,
        candidate_claimed_fill_performance=True,
        candidate_fill_verified=False,
        candidate_counterfactual_pnl_cents=25,
        evidence_reality="SYNTHETIC",
        candidate_marked_promotion_eligible=True,
        candidate_claimed_contested=True,
        claimed_independent_units=2,
        book_valid=False,
        candidate_used_book=True,
        candidate_used_lineup=True,
        lineup_received_at=NOW + timedelta(days=100, minutes=1),
    )
    audit = audit_reward_hacking((task,))
    assert audit.passed is False
    assert {item.trap.value for item in audit.findings} == {
        "LEAKED_TIMESTAMP",
        "DUPLICATED_SOURCE_FAMILY",
        "MISLEADING_MIDPOINT_FILL",
        "SYNTHETIC_DATA",
        "MARKET_PRIOR_AGREEMENT",
        "CLUSTER_INDEPENDENCE",
        "MALFORMED_BOOK",
        "FUTURE_LINEUP",
    }


def test_lineage_bandit_is_cross_lineage_and_greedy_within_lineage() -> None:
    explored = LineageState(
        lineage_id="calibration",
        strategy="calibration-first",
        private_rewards=(0.1, 0.2),
        candidate_scores=(("candidate-a", 0.1), ("candidate-b", 0.2)),
    )
    new_arm = LineageState(
        lineage_id="adversarial",
        strategy="adversarial",
        candidate_scores=(("candidate-c", 0.05), ("candidate-d", 0.07)),
    )
    allocation = allocate_lineage((explored, new_arm))
    assert allocation.selected_lineage_id == "adversarial"
    assert allocation.selected_parent_candidate_id == "candidate-d"

    stalled = replace(
        explored,
        private_rewards=(0.20, 0.201, 0.2015, 0.201),
    )
    fork = propose_stall_fork(
        stalled,
        global_champion_candidate_id="global-champion",
        target_lineage_id="calibration-fork-2",
        target_strategy="abstention-first",
    )
    assert fork is not None
    assert fork.applied is False


def test_context_distillation_is_role_specific_and_private_safe() -> None:
    source = {
        "current_champion": {"id": "champion", "definition": "full"},
        "compact_lineage_summary": {"lineage": "calibration"},
        "historical_attempts": [
            {"hash": f"attempt-{index}", "outcome": "rejected", "noise": "x" * 200}
            for index in range(100)
        ],
        "private_aggregate_receipt": {"fitness": 0.2, "failed_gate_ids": []},
        "irrelevant_full_transcript": "y" * 100_000,
    }
    distilled = distill_context(
        ResearchRole.EVOLUTION_DEBUGGER,
        source,
        max_characters=2_000,
    )
    assert distilled.distilled_characters <= 2_000
    assert distilled.compression_ratio > 16.0
    assert distilled.payload["current_champion"]["id"] == "champion"
    assert "irrelevant_full_transcript" not in distilled.payload
    with pytest.raises(AutoresearchValidationError, match="private item-level"):
        distill_context(
            ResearchRole.EVOLUTION_DEBUGGER,
            {"private_cases": [{"outcome": True}]},
        )


def test_minimizer_requires_private_gain_retention_and_lower_complexity() -> None:
    private_tasks = _suite().partition(EvaluationPartition.PRIVATE_SELECTION)
    original, _ = evaluate_private_selection(
        "original",
        private_tasks,
        complexity_profile=ComplexityProfile(changed_modules=3),
    )
    minimized, _ = evaluate_private_selection(
        "minimized",
        private_tasks,
        complexity_profile=ComplexityProfile(changed_modules=1),
    )
    decision = select_minimized_candidate(
        original,
        minimized,
        original_complexity=ComplexityProfile(changed_modules=3),
        minimized_complexity=ComplexityProfile(changed_modules=1),
        behavioral_spec={
            "inputs": ["frozen_point_in_time_state"],
            "output": "probability_or_abstention",
            "changed_behavior": "market_anchor_weight",
        },
    )
    assert decision.retained_minimized is True
    assert decision.selected_candidate_id == "minimized"
    assert decision.source_edit_applied is False
    assert len(decision.behavioral_spec_digest) == 64


def test_experiment_ledger_detects_tampering(tmp_path) -> None:
    path = tmp_path / "experiments.jsonl"
    ledger = ExperimentLedger(path)
    first = ledger.append("experiment-1", {"fitness": 0.1})
    second = ledger.append("experiment-2", {"fitness": 0.2})
    assert first.previous_hash == "0" * 64
    assert second.previous_hash == first.entry_hash
    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["payload"]["fitness"] = 999
    lines[0] = json.dumps(tampered, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(AutoresearchValidationError, match="tampered"):
        ledger.read_verified()


def _ignition_trial(seed: int, arm: str, *, evolved_win: bool) -> IgnitionTrial:
    evolved = arm == "EVOLVED_OUTER"
    score = 0.30 if evolved and evolved_win else 0.20
    return IgnitionTrial.create(
        arm=arm,
        matched_seed=f"seed-{seed}",
        mutation_budget=10,
        model_access_digest="models",
        evaluator_digest="evaluator",
        target_system_digest="targets",
        wall_compute_budget=100.0,
        starting_genome_digest="genome",
        starting_private_score=0.10,
        best_private_score=score,
        experiments_required=5 if evolved else 8,
        external_transfer_score=0.20 if evolved else 0.15,
        reward_hacking_rate=0.0 if evolved else 0.1,
        complexity_score=5.0 if evolved else 6.0,
        generation=0,
    )


def test_ignition_requires_three_equal_budget_matched_wins_for_level_two() -> None:
    empty = evaluate_ignition(())
    assert empty.highest_supported_level is None
    trials = tuple(
        _ignition_trial(seed, arm, evolved_win=True)
        for seed in range(3)
        for arm in ("MANUAL_OUTER", "EVOLVED_OUTER")
    )
    report = evaluate_ignition(trials)
    assert report.highest_supported_level is IgnitionLevel.IMPROVING_THE_IMPROVER
    assert report.matched_pair_count == 3


def test_outer_researcher_proposes_only_unapplied_constitutional_mutation() -> None:
    policy = ResearchPolicy.create(
        label="manual outer",
        strategy="bandit-lineage",
        lineage_ids=("calibration",),
    )
    researcher = OuterEvolutionResearcher(policy)
    genome = pilot_genomes()[0]
    operation = MutationOperation(
        operator=MutationOperator.SET,
        gene_name="synthesis.market_prior_weight",
        category=GeneCategory.MARKET_PRIOR_WEIGHT,
        value=0.55,
        gene_version="autoresearch-test-v1",
        rationale="test a slightly stronger anchor",
    )
    experiment = researcher.propose_experiment(
        lineage_states=(
            LineageState(
                lineage_id="calibration",
                strategy="calibration-first",
                champion_candidate_id=genome.genome_id,
            ),
        ),
        base_genome=genome,
        level=MutationLevel.PARAMETERS,
        operations=(operation,),
        target_paths=("dummy/genome/candidates/calibration.json",),
        created_at=NOW,
        evidence_ids=("visible-debug-evidence",),
        budget=ResearchBudget(10, 100.0, 100.0, 300),
    )
    assert experiment.mutation_proposal.allowed_by_constitution is True
    assert experiment.source_edit_applied is False
    assert experiment.runtime_application is False
    assert experiment.semantic_dict()["private_item_access"] is False


def test_autoresearch_is_a_protected_surface() -> None:
    paths = {
        item["path"] for item in protected_manifest_dict()["protected_surfaces"]
    }
    assert "dummy/autoresearch" in paths
