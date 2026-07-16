"""Forecast autoresearch adapter for the domain-agnostic intelligence lab."""

from __future__ import annotations

from typing import Any

from dummy.world_model.models import digest_json

from .models import GraphKind, ScientificObservation, make_observation


DOMAIN_ID = "dummy.forecasting"


def _source_id(report: dict[str, Any], fallback: str) -> str:
    return str(report.get("report_id") or report.get("campaign_id") or digest_json({"fallback": fallback, "report": report}))


def observe_forecasting_research(
    *,
    multi_cohort_report: dict[str, Any],
    forward_report: dict[str, Any],
    ignition_report: dict[str, Any],
    observed_at: str,
) -> tuple[ScientificObservation, ...]:
    """Represent only what current artifacts prove; never manufacture outcomes."""
    multi_id = _source_id(multi_cohort_report, "multi")
    forward_id = _source_id(forward_report, "forward")
    ignition_id = _source_id(ignition_report, "ignition")
    schedule = [item for item in multi_cohort_report.get("schedule", []) if isinstance(item, dict)]
    campaigns = [item for item in multi_cohort_report.get("campaigns", []) if isinstance(item, dict)]
    completed = int(multi_cohort_report.get("campaigns_completed") or 0)
    discovered = int(multi_cohort_report.get("discovered_cohorts") or 0)
    private_trials = sum(int((item.get("campaign") or {}).get("genuine_private_candidate_trials") or 0) for item in campaigns)
    private_survivors = sum(int((item.get("campaign") or {}).get("private_survivors") or 0) for item in campaigns)
    external_survivors = sum(int((item.get("campaign") or {}).get("external_survivors") or 0) for item in campaigns)
    forward_settlements = int(forward_report.get("forward_paper_candidate_settlements") or 0)
    supported_level = int(ignition_report.get("highest_supported_recursive_improvement_level") or 0)
    observations = [
        make_observation(
            domain_id=DOMAIN_ID,
            graph_kind=GraphKind.KNOWLEDGE,
            statement=(
                f"The forecasting adapter discovered {discovered} exact cohorts and completed "
                f"{completed} bounded campaigns with {private_trials} private trials."
            ),
            observed_at=observed_at,
            confidence=1.0,
            evidence_ids=(multi_id,),
            attributes={
                "discovered_cohorts": discovered,
                "completed_campaigns": completed,
                "private_trials": private_trials,
            },
        ),
        make_observation(
            domain_id=DOMAIN_ID,
            graph_kind=GraphKind.CAPABILITY,
            statement=(
                "Exact prediction cohorts can be researched autonomously under separate fixed "
                "budgets and prediction-type-specific promotion gates."
            ),
            observed_at=observed_at,
            confidence=1.0,
            evidence_ids=(multi_id,),
            attributes={
                "private_survivors": private_survivors,
                "external_survivors": external_survivors,
                "automatic_positive_promotion": False,
            },
        ),
    ]
    if external_survivors > 0 and forward_settlements == 0:
        observations.append(
            make_observation(
                domain_id=DOMAIN_ID,
                graph_kind=GraphKind.UNKNOWN,
                statement=(
                    f"{external_survivors} external survivor(s) lack settled forward-paper "
                    "confirmation."
                ),
                observed_at=observed_at,
                confidence=1.0,
                evidence_ids=(multi_id, forward_id),
                attributes={
                    "importance": 0.95,
                    "tractability": 0.65,
                    "novelty": 0.35,
                    "missing_evidence": ("settled_forward_paper_clusters", "verified_fills"),
                },
            )
        )
    blocked = [item for item in schedule if str(item.get("status", "")).startswith(("BLOCKED", "ACCUMULATING"))]
    if blocked:
        statuses = sorted({str(item.get("status")) for item in blocked})
        observations.append(
            make_observation(
                domain_id=DOMAIN_ID,
                graph_kind=GraphKind.OPPORTUNITY,
                statement=(
                    f"{len(blocked)} cohort(s) are accumulating prerequisites or blocked by "
                    "missing point-in-time provenance."
                ),
                observed_at=observed_at,
                confidence=1.0,
                evidence_ids=(multi_id,),
                attributes={
                    "importance": 0.8,
                    "tractability": 0.75,
                    "novelty": 0.45,
                    "statuses": tuple(statuses),
                    "missing_evidence": ("causal_horizon_or_phase", "three_partition_evidence"),
                },
            )
        )
    observations.append(
        make_observation(
            domain_id=DOMAIN_ID,
            graph_kind=GraphKind.UNKNOWN,
            statement=(
                f"Recursive-improvement evidence currently supports Level {supported_level}; "
                "higher cognitive levels remain unproven."
            ),
            observed_at=observed_at,
            confidence=1.0,
            evidence_ids=(ignition_id,),
            attributes={
                "importance": 0.9,
                "tractability": 0.4,
                "novelty": 0.8,
                "missing_evidence": (
                    "equal_budget_net_positive_self_improvement",
                    "cross_domain_replication",
                    "improved_improver_ignition_test",
                ),
            },
        )
    )
    return tuple(sorted(observations, key=lambda item: item.observation_id))


__all__ = ["DOMAIN_ID", "observe_forecasting_research"]
