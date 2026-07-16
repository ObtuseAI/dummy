"""Universal, evidence-governed research loop for intelligence itself."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dummy.world_model.models import digest_json, iso

from .discovery import design_experiments, discover_opportunities, generate_hypotheses
from .forecast_domain import observe_forecasting_research
from .models import CognitiveOperator, GraphKind, make_cognitive_genome
from .scientific_memory import ScientificMemory
from .theory import evaluate_theory


MISSION = (
    "Continuously discover, test, validate, and evolve better ways of discovering, "
    "reasoning, creating, researching, planning, and solving under evidence-driven governance."
)

UNIVERSAL_LOOP = (
    "observe",
    "represent",
    "understand",
    "research",
    "imagine",
    "generate",
    "challenge",
    "evaluate",
    "decide",
    "learn",
    "improve",
    "repeat",
)

SEVEN_PILLARS = (
    "discovery",
    "research",
    "computational_creativity",
    "multi_strategy_problem_solving",
    "scientific_method",
    "recursive_cognitive_improvement",
    "theory_building",
)

COGNITIVE_ROLES = (
    "problem_analyst",
    "research_scientist",
    "inventor",
    "systems_thinker",
    "statistician",
    "mathematician",
    "optimizer",
    "skeptic",
    "devils_advocate",
    "simplifier",
    "architect",
    "simulation_designer",
    "experimentalist",
    "theory_builder",
    "knowledge_curator",
    "meta_thinker",
)


def intelligence_lab_manifest() -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": 1,
        "name": "DUMMY_INTELLIGENCE_RESEARCH_LAB",
        "mission": MISSION,
        "optimization_target": "better_evidence_backed_methods_of_discovering",
        "domains_are_experimental_adapters": True,
        "initial_domain": "dummy.forecasting",
        "seven_pillars": list(SEVEN_PILLARS),
        "universal_loop": list(UNIVERSAL_LOOP),
        "cognitive_roles": list(COGNITIVE_ROLES),
        "world_model_graphs": [item.value for item in GraphKind],
        "genome_evolves": [
            "reasoning_strategies",
            "research_methods",
            "problem_solving_templates",
            "creative_operators",
            "planning_algorithms",
            "evaluation_methods",
            "memory_policies",
            "agent_organizations",
        ],
        "constitution_never_evolves": [
            "authority",
            "permissions",
            "truth",
            "settlement",
            "private_evaluator",
            "promotion_law",
            "execution_firewall",
        ],
        "authority": {
            "maximum": "SIMULATE",
            "automatic_positive_promotion": False,
            "human_promotion_required": True,
            "orders_placed": False,
            "execution_authority": False,
            "capital_authority": False,
        },
        "scientific_method": [
            "observation",
            "question",
            "hypothesis",
            "prediction",
            "preregistration",
            "experiment",
            "measurement",
            "analysis",
            "independent_replication",
            "theory_gate",
            "publication_candidate",
        ],
        "theory_gate": {
            "provisional_theory": "three_valid_replications_across_two_domains",
            "general_law": "six_valid_replications_across_three_domains",
            "positive_effect_lower_bound_required": True,
            "fixed_cost_required": True,
            "calibration_noninferiority_required": True,
            "reward_hack_audit_required": True,
            "deterministic_replay_required": True,
        },
    }
    body["manifest_id"] = digest_json(body)
    return body


def baseline_cognitive_genome() -> Any:
    return make_cognitive_genome(
        label="evidence-governed cognitive research generation zero",
        generation=0,
        parent_genome_ids=(),
        reasoning_strategies=(
            "adversarial_decomposition",
            "competing_strategy_search",
            "uncertainty_first_metacognition",
        ),
        research_methods=(
            "fixed_budget_preregistration",
            "hidden_selection_evidence",
            "independent_replication",
            "point_in_time_causal_replay",
        ),
        creative_operators=tuple(CognitiveOperator),
        evaluation_methods=(
            "complexity_adjusted_pareto_selection",
            "cross_domain_external_generalization",
            "reward_hacking_canaries",
        ),
        memory_policies=(
            "content_addressed_records",
            "hash_chained_scientific_memory",
            "role_specific_context_distillation",
            "theories_over_transcripts",
        ),
        agent_organization=COGNITIVE_ROLES,
    )


def _level_report(*, has_domain_work: bool, valid_receipts: int) -> list[dict[str, Any]]:
    definitions = (
        (0, "solve_problems", has_domain_work, "bounded domain work exists"),
        (1, "improve_problem_solving", valid_receipts >= 3, "three valid fixed-cost replications"),
        (2, "improve_research", False, "equal-budget research-method improvement"),
        (3, "improve_creativity", False, "held-out creative-method improvement"),
        (4, "improve_reasoning", False, "cross-domain reasoning transfer"),
        (5, "improve_improvement", False, "evolved improver beats frozen improver"),
        (6, "improve_discovery", False, "novel opportunities yield replicated value"),
        (7, "improve_intelligence_evolution", False, "accelerating gains under fixed physical budget"),
    )
    return [
        {"level": level, "purpose": purpose, "supported": supported, "gate": gate}
        for level, purpose, supported, gate in definitions
    ]


def _node(kind: GraphKind, record_id: str, label: str, domain_id: str) -> dict[str, str]:
    return {"kind": kind.value, "record_id": record_id, "label": label, "domain_id": domain_id}


def _challenge_assessment(hypothesis: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": 1,
        "hypothesis_id": hypothesis.hypothesis_id,
        "domain_id": hypothesis.domain_id,
        "roles": {
            "skeptic": "identify the strongest evidence that would make the claim false",
            "devils_advocate": "construct the strongest reward-hacking explanation for apparent gain",
            "statistician": "challenge independence, uncertainty, multiplicity, and effect size",
            "systems_thinker": "trace second-order effects and correlated source families",
            "simplifier": "find the minimum method that preserves any measured gain",
        },
        "required_checks": [
            "future_leakage",
            "forced_coverage_contamination",
            "selective_abstention",
            "market_selection_bias",
            "source_family_duplication",
            "simulator_exploitation",
            "fill_truth_regression",
            "compute_inflation",
            "complexity_growth",
        ],
        "status": "PENDING_PROTECTED_EVALUATION",
        "candidate_controls_challenge": False,
    }
    body["challenge_id"] = digest_json(body)
    return body


def run_intelligence_research_cycle(
    *,
    multi_cohort_report: dict[str, Any],
    forward_report: dict[str, Any],
    ignition_report: dict[str, Any],
    output_dir: Path,
    observed_at: datetime,
) -> dict[str, Any]:
    """Run one deterministic observe-to-research cycle over domain evidence."""
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    timestamp = iso(observed_at.astimezone(timezone.utc))
    observations = observe_forecasting_research(
        multi_cohort_report=multi_cohort_report,
        forward_report=forward_report,
        ignition_report=ignition_report,
        observed_at=timestamp,
    )
    opportunities = discover_opportunities(observations)
    hypotheses = generate_hypotheses(opportunities)
    experiments = design_experiments(hypotheses)
    challenges = [_challenge_assessment(item) for item in hypotheses]
    genome = baseline_cognitive_genome()
    theories = [
        evaluate_theory(
            hypothesis_id=hypothesis.hypothesis_id,
            claim=hypothesis.claim,
            receipts=(),
        )
        for hypothesis in hypotheses
    ]

    memory = ScientificMemory(output_dir / "scientific_memory.jsonl")
    appended = 0
    for record_type, records in (
        ("observation", [item.to_dict() for item in observations]),
        ("opportunity", [item.to_dict() for item in opportunities]),
        ("hypothesis", [item.to_dict() for item in hypotheses]),
        ("experiment_protocol", [item.to_dict() for item in experiments]),
        ("adversarial_challenge", challenges),
        ("theory_assessment", theories),
        ("cognitive_genome", [genome.to_dict()]),
    ):
        for payload in records:
            _, created = memory.append_unique(record_type=record_type, payload=payload)
            appended += int(created)

    nodes = [
        *[_node(item.graph_kind, item.observation_id, item.statement, item.domain_id) for item in observations],
        *[_node(GraphKind.OPPORTUNITY, item.opportunity_id, item.question, item.domain_id) for item in opportunities],
        *[_node(GraphKind.HYPOTHESIS, item.hypothesis_id, item.claim, item.domain_id) for item in hypotheses],
        *[_node(GraphKind.RESEARCH, item.experiment_id, item.intervention, item.domain_id) for item in experiments],
    ]
    edges = [
        {
            "from": source_id,
            "to": opportunity.opportunity_id,
            "relation": "motivates",
        }
        for opportunity in opportunities
        for source_id in opportunity.source_observation_ids
    ]
    edges.extend(
        {
            "from": hypothesis.opportunity_id,
            "to": hypothesis.hypothesis_id,
            "relation": f"generated_by_{hypothesis.operator.value}",
        }
        for hypothesis in hypotheses
    )
    edges.extend(
        {"from": item.hypothesis_id, "to": item.experiment_id, "relation": "tested_by"}
        for item in experiments
    )
    levels = _level_report(has_domain_work=bool(observations), valid_receipts=0)
    report: dict[str, Any] = {
        "schema_version": 1,
        "name": "DUMMY_INTELLIGENCE_OBSERVATORY",
        "mission": MISSION,
        "cycle_observed_at": timestamp,
        "manifest_id": intelligence_lab_manifest()["manifest_id"],
        "universal_loop": list(UNIVERSAL_LOOP),
        "domain_adapters": ["dummy.forecasting"],
        "scope_limit": (
            "The world model contains only evidence ingested by registered adapters; it does "
            "not claim complete knowledge of humanity."
        ),
        "current_cognitive_genome": genome.to_dict(),
        "cognitive_state": {
            "observations": len(observations),
            "opportunities": len(opportunities),
            "hypotheses": len(hypotheses),
            "proposed_experiments": len(experiments),
            "pending_adversarial_challenges": len(challenges),
            "completed_experiments": 0,
            "valid_replications": 0,
            "provisional_theories": 0,
            "general_laws": 0,
            "new_scientific_memory_entries": appended,
        },
        "research_queue": [item.to_dict() for item in experiments],
        "adversarial_challenges": challenges,
        "opportunity_queue": [item.to_dict() for item in opportunities],
        "hypotheses": [item.to_dict() for item in hypotheses],
        "theory_assessments": theories,
        "knowledge_graph": {
            "graph_kinds": [item.value for item in GraphKind],
            "nodes": sorted(nodes, key=lambda item: (item["kind"], item["record_id"])),
            "edges": sorted(edges, key=lambda item: (item["from"], item["to"], item["relation"])),
        },
        "recursive_levels": levels,
        "highest_supported_level": max(item["level"] for item in levels if item["supported"]),
        "metacognition": {
            "understanding_complete": False,
            "overconfidence_allowed": False,
            "unresolved_unknowns": sum(item.graph_kind is GraphKind.UNKNOWN for item in observations),
            "stop_reason": "await_protected_experiment_and_replication_evidence",
            "invent_new_method_when_stalled": True,
        },
        "claims": {
            "new_intelligence_method_validated": False,
            "recursive_self_improvement_supported": False,
            "improved_improver_supported": False,
            "accelerating_improvement_supported": False,
        },
        "automatic_positive_promotion": False,
        "human_promotion_required": True,
        "orders_placed": False,
        "execution_authority": False,
        "capital_authority": False,
    }
    report["report_id"] = digest_json(report)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "observatory_report.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    queue: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": timestamp,
        "source_report_id": report["report_id"],
        "scheduling_policy": "importance_x_tractability_x_novelty_then_content_id",
        "fixed_compute_budget_per_experiment": 1_000.0,
        "total_proposed_compute_budget": sum(item.compute_budget for item in experiments),
        "protocols": [item.to_dict() for item in experiments],
        "automatic_execution_scope": "PROTECTED_SHADOW_SIMULATION_ONLY",
        "automatic_positive_promotion": False,
        "execution_authority": False,
    }
    queue["queue_id"] = digest_json(queue)
    queue_path = output_dir / "research_queue.json"
    queue_temporary = queue_path.with_suffix(".tmp")
    queue_temporary.write_text(
        json.dumps(queue, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    queue_temporary.replace(queue_path)
    return report


__all__ = [
    "COGNITIVE_ROLES",
    "MISSION",
    "SEVEN_PILLARS",
    "UNIVERSAL_LOOP",
    "baseline_cognitive_genome",
    "intelligence_lab_manifest",
    "run_intelligence_research_cycle",
]
