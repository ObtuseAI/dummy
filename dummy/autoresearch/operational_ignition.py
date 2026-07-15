"""Persistent, fixed-budget ignition evidence derived from real campaigns."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dummy.world_model.models import digest_json

from .experiment_ledger import ExperimentLedger
from .ignition_test import IgnitionLevel, IgnitionTrial, evaluate_ignition
from .private_evaluator import private_evaluator_manifest


def campaign_ignition_trial(
    campaign: dict[str, Any],
    *,
    arm: str = "MANUAL_OUTER",
    generation: int = 0,
) -> IgnitionTrial:
    candidates = list(campaign.get("candidates") or [])
    if not candidates:
        raise ValueError("ignition trial requires a completed campaign")
    best_index, best = max(
        enumerate(candidates, start=1),
        key=lambda item: float((item[1].get("private_receipt") or {}).get("fitness", -1e9)),
    )
    private_score = float((best.get("private_receipt") or {}).get("fitness", -1.0))
    external = best.get("external_evaluation") or {}
    external_metrics = external.get("metrics") or {}
    external_transfer = float(external_metrics.get("cross_regime_transfer", -1.0))
    hacking_failures = sum(
        "reward_hacking_traps_clear"
        in set((candidate.get("private_receipt") or {}).get("failed_gate_ids") or [])
        for candidate in candidates
    )
    budget = campaign.get("budget") or {}
    maximum_experiments = int(budget.get("maximum_experiments") or len(candidates))
    per_experiment = float(budget.get("per_experiment_compute_units") or 1.0)
    return IgnitionTrial.create(
        arm=arm,
        matched_seed=str((campaign.get("partition_plan") or {}).get("evidence_fingerprint")),
        mutation_budget=maximum_experiments,
        model_access_digest=digest_json(
            {
                "model_access": "recorded_genome_replay_only",
                "language_model_calls": 0,
                "external_model_calls": 0,
            }
        ),
        evaluator_digest=str(private_evaluator_manifest()["manifest_id"]),
        target_system_digest=digest_json(
            {
                "scope": campaign.get("scope"),
                "partition_plan_id": (campaign.get("partition_plan") or {}).get(
                    "plan_id"
                ),
            }
        ),
        wall_compute_budget=maximum_experiments * per_experiment,
        starting_genome_digest=str(campaign["base_genome_id"]),
        starting_private_score=0.0,
        best_private_score=private_score,
        experiments_required=best_index,
        external_transfer_score=external_transfer,
        reward_hacking_rate=hacking_failures / len(candidates),
        complexity_score=float(best.get("complexity_score") or 0.0),
        generation=generation,
    )


def record_campaign_ignition_trial(
    campaign: dict[str, Any],
    *,
    trial_ledger_path: Path,
    arm: str = "MANUAL_OUTER",
    generation: int = 0,
) -> IgnitionTrial:
    trial = campaign_ignition_trial(campaign, arm=arm, generation=generation)
    ledger = ExperimentLedger(trial_ledger_path)
    existing = ledger.read_verified()
    if not any(entry.experiment_id == trial.trial_id for entry in existing):
        ledger.append(trial.trial_id, trial.to_dict())
    return trial


def operational_ignition_report(
    *,
    trial_ledger_path: Path,
    forward_report: dict[str, Any],
) -> dict[str, Any]:
    ledger = ExperimentLedger(trial_ledger_path)
    trials = tuple(
        IgnitionTrial.from_dict(dict(entry.payload))
        for entry in ledger.read_verified()
    )
    experimental = evaluate_ignition(trials)
    forward_confirmed = bool(
        forward_report.get("ready_for_human_promotion_review")
        and int(forward_report.get("forward_paper_candidate_settlements") or 0) >= 100
        and int(forward_report.get("event_clusters") or 0) >= 10
        and int(forward_report.get("verified_settled_fills") or 0) >= 5
    )
    experimental_level = experimental.highest_supported_level
    operational_level = experimental_level
    if (
        operational_level is not None
        and operational_level >= IgnitionLevel.NET_POSITIVE_SELF_IMPROVEMENT
        and not forward_confirmed
    ):
        operational_level = IgnitionLevel.AUTONOMOUS_EXPERIMENTATION
    level1_supported = bool(
        operational_level is not None
        and operational_level >= IgnitionLevel.NET_POSITIVE_SELF_IMPROVEMENT
    )
    matched_pairs = experimental.matched_pair_count
    body: dict[str, Any] = {
        "schema_version": 1,
        "trial_count": len(trials),
        "campaign_trial_ids": [trial.trial_id for trial in trials],
        "experimental_ignition": experimental.to_dict(),
        "forward_confirmation_passed": forward_confirmed,
        "highest_supported_recursive_improvement_level": (
            int(operational_level) if operational_level is not None else None
        ),
        "highest_supported_label": (
            operational_level.name if operational_level is not None else "NOT_EVALUATED"
        ),
        "level1_net_positive_self_improvement_supported": level1_supported,
        "level2_matched_ab_test": {
            "eligible": level1_supported,
            "matched_pairs_completed": matched_pairs,
            "status": (
                "EVALUATED"
                if matched_pairs
                else (
                    "READY_FOR_FIXED_BUDGET_AB_TEST"
                    if level1_supported
                    else "BLOCKED_UNTIL_LEVEL1_AND_FORWARD_CONFIRMATION"
                )
            ),
            "required_equalities": [
                "mutation_budget",
                "model_access",
                "private_evaluator",
                "target_systems",
                "wall_compute_budget",
                "starting_genomes",
                "starting_private_score",
            ],
        },
        "self_improvement_claim_supported": level1_supported,
        "improved_improver_claim_supported": bool(
            operational_level is not None
            and operational_level >= IgnitionLevel.IMPROVING_THE_IMPROVER
        ),
        "accelerating_improvement_claim_supported": bool(
            operational_level is IgnitionLevel.ACCELERATING_IMPROVEMENT
        ),
        "automatic_promotion": False,
        "execution_authority": False,
        "capital_authority": False,
    }
    body["report_id"] = digest_json(body)
    return body


def write_ignition_report(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


__all__ = [
    "campaign_ignition_trial",
    "operational_ignition_report",
    "record_campaign_ignition_trial",
    "write_ignition_report",
]
