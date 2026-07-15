"""Protected evaluator for purged, cluster-corrected evolutionary claims."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from dummy.genome import GenomeFitness
from dummy.truth import (
    BaselineSet,
    causal_attribution_report,
    clustered_mean_test,
    contested_rows,
    holm_bonferroni,
)
from dummy.world_model.models import digest_json

from .candidate import CandidateEvaluationInput


EVALUATOR_VERSION = "phase6-causal-evolution-evaluator-v1"


def _mean(values: tuple[float, ...]) -> float | None:
    return round(sum(values) / len(values), 12) if values else None


def _candidate_raw(
    item: CandidateEvaluationInput,
    *,
    minimum_clusters: int,
    minimum_transfer_clusters: int,
    bootstrap_simulations: int,
    permutation_draws: int,
) -> dict[str, Any]:
    cases = item.held_out_cases
    outcome = tuple(float(case.result_yes) for case in cases)
    candidate_brier = tuple(
        (case.candidate_probability - result) ** 2
        for case, result in zip(cases, outcome, strict=True)
    )
    incumbent_brier = tuple(
        (case.incumbent_probability - result) ** 2
        for case, result in zip(cases, outcome, strict=True)
    )
    market_brier = tuple(
        (case.market_prior_probability - result) ** 2
        for case, result in zip(cases, outcome, strict=True)
    )
    incumbent_gains = tuple(
        (case.event_cluster_id, incumbent - candidate)
        for case, incumbent, candidate in zip(
            cases,
            incumbent_brier,
            candidate_brier,
            strict=True,
        )
    )
    clustered = clustered_mean_test(
        incumbent_gains,
        bootstrap_simulations=bootstrap_simulations,
        permutation_draws=permutation_draws,
    )
    contested = contested_rows(
        tuple(
            (
                case.event_cluster_id,
                case.candidate_probability,
                case.market_prior_probability,
                result,
            )
            for case, result in zip(cases, outcome, strict=True)
        )
    )
    contested_clustered = clustered_mean_test(
        contested,
        bootstrap_simulations=bootstrap_simulations,
        permutation_draws=permutation_draws,
    )
    by_transfer: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for case, incumbent, candidate in zip(
        cases,
        incumbent_brier,
        candidate_brier,
        strict=True,
    ):
        if case.transfer_group != item.primary_transfer_group:
            by_transfer[case.transfer_group].append(
                (case.event_cluster_id, incumbent - candidate)
            )
    transfer_reports = {}
    for group, rows in sorted(by_transfer.items()):
        report = clustered_mean_test(
            tuple(rows),
            bootstrap_simulations=bootstrap_simulations,
            permutation_draws=permutation_draws,
        )
        transfer_reports[group] = {
            **report.to_dict(),
            "minimum_event_clusters": minimum_transfer_clusters,
            "passes": (
                report.event_cluster_count >= minimum_transfer_clusters
                and report.positive_interval
            ),
        }
    transfer_passed = bool(transfer_reports) and all(
        report["passes"] for report in transfer_reports.values()
    )
    cluster_count = len({case.event_cluster_id for case in cases})
    enough = cluster_count >= minimum_clusters
    raw_gain = _mean(
        tuple(
            incumbent - candidate
            for incumbent, candidate in zip(
                incumbent_brier,
                candidate_brier,
                strict=True,
            )
        )
    )
    market_gain = _mean(
        tuple(
            market - candidate
            for market, candidate in zip(
                market_brier,
                candidate_brier,
                strict=True,
            )
        )
    )
    return {
        "candidate_id": item.candidate.genome_id,
        "mutation_proposal_id": item.mutation_proposal.proposal_id,
        "baseline_set": BaselineSet(
            incumbent_id=item.incumbent_id,
            market_prior_id=item.market_prior_id,
            candidate_id=item.candidate.genome_id,
        ).to_dict(),
        "held_out_case_count": len(cases),
        "held_out_event_cluster_count": cluster_count,
        "minimum_event_clusters": minimum_clusters,
        "training_event_cluster_count": len(item.training_event_cluster_ids),
        "event_cluster_purged": True,
        "selection_evidence_purged": True,
        "raw_brier_gain_vs_incumbent": raw_gain,
        "raw_brier_gain_vs_market_prior": market_gain,
        "clustered_gain_vs_incumbent": clustered.to_dict(),
        "contested_gain_vs_market_prior": contested_clustered.to_dict(),
        "transfer_reports": transfer_reports,
        "transfer_passed": transfer_passed,
        "enough_evidence": enough,
        "point_in_time_verified": all(case.point_in_time_verified for case in cases),
        "settlement_verified": all(case.settlement_verified for case in cases),
        "deterministic_replay_verified": item.deterministic_replay_verified,
        "replay_report_id": item.replay_report_id,
        "governance_preserved": item.governance_preserved,
        "governance_report_id": item.governance_report_id,
        "raw_one_sided_p_value": clustered.one_sided_p_value,
        "evidence_ids": sorted(
            {
                item.replay_report_id,
                item.governance_report_id,
                *item.candidate_selection_evidence_ids,
                *(evidence for case in cases for evidence in case.evidence_ids),
            }
        ),
    }


def evaluate_evolution_family(
    candidates: tuple[CandidateEvaluationInput, ...],
    *,
    minimum_clusters: int = 30,
    minimum_transfer_clusters: int = 10,
    bootstrap_simulations: int = 4_000,
    permutation_draws: int = 8_000,
) -> dict[str, Any]:
    ordered = tuple(sorted(candidates, key=lambda item: item.candidate.genome_id))
    ids = tuple(item.candidate.genome_id for item in ordered)
    if len(set(ids)) != len(ids):
        raise ValueError("evolution family contains duplicate candidate IDs")
    raw = tuple(
        _candidate_raw(
            item,
            minimum_clusters=minimum_clusters,
            minimum_transfer_clusters=minimum_transfer_clusters,
            bootstrap_simulations=bootstrap_simulations,
            permutation_draws=permutation_draws,
        )
        for item in ordered
    )
    corrected = holm_bonferroni(
        tuple(
            (
                str(report["candidate_id"]),
                float(report["raw_one_sided_p_value"])
                if report["raw_one_sided_p_value"] is not None
                else 1.0,
            )
            for report in raw
        )
    )
    corrections = {item.hypothesis_id: item for item in corrected}
    reports = []
    fitness = []
    for report in raw:
        correction = corrections[str(report["candidate_id"])]
        clustered = report["clustered_gain_vs_incumbent"]
        contested = report["contested_gain_vs_market_prior"]
        supported = bool(
            report["enough_evidence"]
            and clustered["positive_interval"]
            and contested["positive_interval"]
            and report["transfer_passed"]
            and correction.rejected_null
            and report["point_in_time_verified"]
            and report["settlement_verified"]
            and report["deterministic_replay_verified"]
            and report["governance_preserved"]
        )
        status = (
            "HELD_OUT_IMPROVEMENT_SUPPORTED"
            if supported
            else "INSUFFICIENT_SETTLED_EVIDENCE"
            if not report["enough_evidence"]
            else "INSUFFICIENT_EDGE_EVIDENCE"
        )
        attribution = causal_attribution_report(
            candidate_id=str(report["candidate_id"]),
            raw_brier_gain=report["raw_brier_gain_vs_incumbent"],
            contested_brier_gain=contested["observed_mean"],
            clustered=clustered_mean_test(
                tuple(
                    (
                        case.event_cluster_id,
                        (case.incumbent_probability - float(case.result_yes)) ** 2
                        - (case.candidate_probability - float(case.result_yes)) ** 2,
                    )
                    for item in ordered
                    if item.candidate.genome_id == report["candidate_id"]
                    for case in item.held_out_cases
                ),
                bootstrap_simulations=bootstrap_simulations,
                permutation_draws=permutation_draws,
            ),
            transfer_passed=bool(report["transfer_passed"]),
            multiple_testing_passed=correction.rejected_null,
            point_in_time_verified=bool(report["point_in_time_verified"]),
            fill_truth_separate=True,
        )
        complete = {
            **report,
            "multiple_testing": correction.to_dict(),
            "causal_attribution": attribution,
            "verdict": status,
            "eligible_for_human_review": supported,
            "eligible_for_promotion": False,
            "automatic_promotion": False,
            "applied": False,
        }
        complete["report_id"] = digest_json(complete)
        reports.append(complete)
        interval = clustered["confidence_interval"]
        fitness.append(
            GenomeFitness.create(
                genome_id=str(report["candidate_id"]),
                evaluator_version=EVALUATOR_VERSION,
                held_out_event_clusters=int(report["held_out_event_cluster_count"]),
                raw_brier_gain=report["raw_brier_gain_vs_incumbent"],
                cluster_adjusted_gain=clustered["observed_mean"],
                confidence_interval=tuple(interval) if interval is not None else None,
                corrected_p_value=correction.adjusted_p_value,
                transfer_passed=bool(report["transfer_passed"]),
                governance_preserved=bool(report["governance_preserved"]),
                verdict=status,
                evidence_ids=tuple(report["evidence_ids"]),
            ).to_dict()
        )
    status = (
        "EVALUATED"
        if reports and any(report["enough_evidence"] for report in reports)
        else "INSUFFICIENT_SETTLED_EVIDENCE"
    )
    body: dict[str, Any] = {
        "schema_version": 1,
        "evaluator_version": EVALUATOR_VERSION,
        "status": status,
        "candidate_count": len(reports),
        "candidate_reports": reports,
        "fitness_records": fitness,
        "multiple_testing_method": "HOLM_BONFERRONI",
        "held_out_only": True,
        "candidate_controls_evaluator": False,
        "promotion_authority": "HUMAN_ONLY",
        "automatic_promotion": False,
    }
    body["family_report_id"] = digest_json(body)
    return body


__all__ = ["EVALUATOR_VERSION", "evaluate_evolution_family"]
