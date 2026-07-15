"""Emit deterministic nested autoresearch policy and evidence artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dummy.autoresearch.complexity_gate import (  # noqa: E402
    complexity_policy_manifest,
)
from dummy.autoresearch.campaign import LOOP1_LINEAGES  # noqa: E402
from dummy.autoresearch.context_distiller import (  # noqa: E402
    context_policy_manifest,
)
from dummy.autoresearch.ignition_test import evaluate_ignition  # noqa: E402
from dummy.autoresearch.orchestrator import lifecycle_manifest  # noqa: E402
from dummy.autoresearch.outer_researcher import (  # noqa: E402
    outer_researcher_manifest,
)
from dummy.autoresearch.private_evaluator import (  # noqa: E402
    private_evaluator_manifest,
)
from dummy.autoresearch.reward_hacking_detector import (  # noqa: E402
    reward_hacking_manifest,
)
from dummy.autoresearch.task_suite import (  # noqa: E402
    task_suite_policy_manifest,
)
from dummy.constitution import protected_manifest_digest  # noqa: E402
from dummy.world_model.models import digest_json  # noqa: E402


def autoresearch_policy_manifest() -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": 1,
        "maturity": "EXPERIMENTAL_SOVEREIGN_FORECASTING",
        "name": "AIDE2_STYLE_FORECAST_RESEARCH_IMPROVEMENT_LOOP",
        "nested_loops": [
            {
                "level": 0,
                "purpose": "forecast_and_settle_markets",
                "authority": "SHADOW_AND_EXISTING_GOVERNED_RUNTIME_ONLY",
            },
            {
                "level": 1,
                "purpose": "improve_forecast_research_organisms",
                "authority": "PROPOSE_SIMULATE_EVALUATE",
            },
            {
                "level": 2,
                "purpose": "improve_how_organisms_are_improved",
                "authority": "PROPOSAL_ONLY_POLICY_GENOMES",
            },
            {
                "level": 3,
                "purpose": "test_whether_improvement_rate_accelerates",
                "authority": "OBSERVE_AND_REPORT_ONLY",
            },
        ],
        "evaluation_hierarchy": [
            "formal_invariants_and_deterministic_checks",
            "hidden_point_in_time_settlement_evidence",
            "external_held_out_generalization",
            "forward_paper_evidence",
            "independent_adversarial_models",
            "intrinsic_model_confidence",
        ],
        "components": {
            "outer_researcher": outer_researcher_manifest(),
            "task_suite": task_suite_policy_manifest(),
            "private_evaluator": private_evaluator_manifest(),
            "reward_hacking": reward_hacking_manifest(),
            "complexity": complexity_policy_manifest(),
            "context": context_policy_manifest(),
            "candidate_lifecycle": lifecycle_manifest(),
            "real_ledger_pipeline": {
                "sqlite_mode": "READ_ONLY_QUERY_ONLY",
                "decision_selection": "EARLIEST_PRE_SETTLEMENT_DECISION_PER_MARKET",
                "partitioning": "CHRONOLOGICAL_WHOLE_DATE",
                "event_cluster_cross_partition_purge": True,
                "settlement_receipt_as_conservative_close_upper_bound": True,
                "candidate_controls_partition": False,
                "forced_coverage_private_selection_eligible": False,
                "exact_cohort_schema": (
                    "vertical|subject|market_type|horizon_or_phase"
                ),
                "cross_cohort_evidence_transfer": False,
            },
            "loop1_campaign": {
                "lineages": list(LOOP1_LINEAGES),
                "one_initial_trial_per_lineage": True,
                "same_starting_genome": True,
                "same_private_evaluator": True,
                "same_compute_budget": True,
                "private_item_feedback_to_outer": False,
                "semantic_minimization_after_private_survival": True,
                "external_evaluation_after_private_survival_only": True,
            },
            "forward_paper": {
                "candidate_frozen_before_new_decisions": True,
                "issue_only_while_unsettled": True,
                "hash_chained_observation_ledger": True,
                "issued_before_settlement_required": True,
                "deterministic_replay_required": True,
                "exact_recorded_decision_required_to_inherit_fill": True,
                "counterfactual_avoided_pnl_is_verified_fill": False,
                "orders_placed": False,
                "broker_contact": False,
                "one_frozen_exact_cohort_per_registry": True,
            },
        },
        "protected_manifest_digest": protected_manifest_digest(),
        "source_edits_applied": False,
        "runtime_application": False,
        "automatic_promotion": False,
        "promotion_authority": "HUMAN_ONLY",
        "execution_authority": False,
    }
    body["manifest_id"] = digest_json(body)
    return body


def autoresearch_evidence_manifest(
    campaign: dict[str, object] | None = None,
    forward: dict[str, object] | None = None,
    ignition: dict[str, object] | None = None,
) -> dict[str, object]:
    campaign = campaign or {}
    forward = forward or {}
    ignition = ignition or evaluate_ignition(()).to_dict()
    private_trials = int(campaign.get("genuine_private_candidate_trials") or 0)
    external_trials = int(
        campaign.get("genuine_external_generalization_trials") or 0
    )
    forward_settlements = int(
        forward.get("forward_paper_candidate_settlements") or 0
    )
    highest = ignition.get("highest_supported_recursive_improvement_level")
    if highest is None:
        highest = ignition.get("highest_supported_level")
    level1 = bool(ignition.get("self_improvement_claim_supported"))
    performance = bool(forward.get("performance_claim_supported"))
    candidate_summaries = [
        {
            "lineage_id": item.get("lineage_id"),
            "candidate_genome_id": (item.get("candidate_genome") or {}).get(
                "genome_id"
            ),
            "private_receipt": item.get("private_receipt"),
            "private_selected": item.get("private_selected"),
            "external_passed": item.get("external_passed"),
            "forward_paper_eligible": item.get("forward_paper_eligible"),
            "complexity_score": item.get("complexity_score"),
            "compute_units_used": item.get("compute_units_used"),
        }
        for item in campaign.get("candidates", [])
    ]
    body: dict[str, object] = {
        "schema_version": 1,
        "maturity": "EXPERIMENTAL_SOVEREIGN_FORECASTING",
        "mechanics_implemented": True,
        "genuine_private_candidate_trials": private_trials,
        "genuine_external_generalization_trials": external_trials,
        "forward_paper_candidate_settlements": forward_settlements,
        "campaign": {
            "campaign_id": campaign.get("campaign_id"),
            "scope": campaign.get("scope"),
            "partition_plan": campaign.get("partition_plan"),
            "budget": campaign.get("budget"),
            "private_survivors": campaign.get("private_survivors", 0),
            "external_survivors": campaign.get("external_survivors", 0),
            "best_forward_candidate_id": campaign.get("best_forward_candidate_id"),
            "candidate_summaries": candidate_summaries,
            "unavailable_lineages": campaign.get("unavailable_lineages", []),
            "private_item_details": None,
        },
        "forward": {
            "status": forward.get("status", "NOT_STARTED"),
            "issued_observations": forward.get("issued_observations", 0),
            "event_clusters": forward.get("event_clusters", 0),
            "verified_settled_fills": forward.get("verified_settled_fills", 0),
            "ready_for_human_promotion_review": forward.get(
                "ready_for_human_promotion_review", False
            ),
        },
        "ignition": ignition,
        "highest_supported_recursive_improvement_level": highest,
        "status": (
            "LEVEL0_AUTONOMOUS_EXPERIMENTATION_LEVEL1_NOT_SUPPORTED"
            if highest == 0 and not level1
            else "MECHANICS_VALIDATED_EMPIRICAL_GATES_OPEN"
        ),
        "performance_claim_supported": performance,
        "self_improvement_claim_supported": level1,
        "improved_improver_claim_supported": bool(
            ignition.get("improved_improver_claim_supported")
        ),
        "accelerating_improvement_claim_supported": bool(
            ignition.get("accelerating_improvement_claim_supported")
        ),
        "live_readiness_changed": False,
        "source_edits_applied": False,
        "runtime_application": False,
        "automatic_promotion": False,
        "execution_authority": False,
    }
    body["evidence_id"] = digest_json(body)
    return body


def build_outputs(
    campaign: dict[str, object] | None = None,
    forward: dict[str, object] | None = None,
    ignition: dict[str, object] | None = None,
) -> dict[str, dict[str, object]]:
    outputs = {
        "VNEXT_AUTORESEARCH_POLICY.json": autoresearch_policy_manifest(),
        "VNEXT_AUTORESEARCH_EVIDENCE.json": autoresearch_evidence_manifest(
            campaign,
            forward,
            ignition,
        ),
    }
    if campaign is not None:
        outputs["VNEXT_AUTORESEARCH_CAMPAIGN.json"] = campaign
    if forward is not None:
        outputs["VNEXT_AUTORESEARCH_FORWARD_EVIDENCE.json"] = forward
    if ignition is not None:
        outputs["VNEXT_AUTORESEARCH_IGNITION.json"] = ignition
    return outputs


def _read_json(path: Path | None) -> dict[str, object] | None:
    if path is None or not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs")
    runtime = ROOT / "runtime" / "autonomy" / "autoresearch"
    parser.add_argument(
        "--campaign-report",
        type=Path,
        default=runtime / "campaign_report.json",
    )
    parser.add_argument(
        "--forward-report",
        type=Path,
        default=runtime / "forward_report.json",
    )
    parser.add_argument(
        "--ignition-report",
        type=Path,
        default=runtime / "ignition_report.json",
    )
    args = parser.parse_args()
    campaign = _read_json(args.campaign_report)
    forward = _read_json(args.forward_report)
    ignition = _read_json(args.ignition_report)
    outputs = build_outputs(campaign, forward, ignition)
    for filename, payload in outputs.items():
        _write(args.output_dir / filename, payload)
    print(
        json.dumps(
            {
                "outputs": [str(args.output_dir / name) for name in outputs],
                "genuine_private_candidate_trials": int(
                    (campaign or {}).get("genuine_private_candidate_trials") or 0
                ),
                "highest_supported_recursive_improvement_level": (
                    (ignition or {}).get(
                        "highest_supported_recursive_improvement_level"
                    )
                ),
                "empirical_recursive_improvement_claim": bool(
                    (ignition or {}).get("self_improvement_claim_supported")
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
