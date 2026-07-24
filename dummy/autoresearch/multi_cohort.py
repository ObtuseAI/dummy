"""Autonomous exact-cohort discovery and bounded Loop-1 scheduling."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

from dummy.genome import ForecastGenome, Gene, GeneCategory, pilot_genomes
from dummy.world_model.models import digest_json

from .campaign import run_loop1_campaign, write_campaign_report
from .ledger_pipeline import (
    LedgerEvidenceRow,
    build_ledger_partition_plan,
)
from .models import AutoresearchValidationError


@dataclass(frozen=True, slots=True)
class CohortCandidate:
    scope: str
    rows: tuple[LedgerEvidenceRow, ...]
    decision_dates: int


def discover_exact_cohorts(
    rows: Iterable[LedgerEvidenceRow],
) -> tuple[CohortCandidate, ...]:
    grouped: dict[str, list[LedgerEvidenceRow]] = {}
    for row in rows:
        grouped.setdefault(row.cohort_scope, []).append(row)
    return tuple(
        CohortCandidate(
            scope=scope,
            rows=tuple(
                sorted(scoped, key=lambda item: (item.decision_at, item.market_ticker))
            ),
            decision_dates=len({row.decision_at.date() for row in scoped}),
        )
        for scope, scoped in sorted(grouped.items())
    )


def _scope_parts(scope: str) -> tuple[str, str, str, str]:
    parts = tuple(scope.split("|"))
    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError(f"invalid exact cohort scope: {scope!r}")
    return parts  # type: ignore[return-value]


def cohort_ticker_prefix(scope: str) -> str | None:
    vertical, subject, _market_type, _axis = _scope_parts(scope)
    if vertical == "crypto" and subject in {"btc", "eth", "sol"}:
        return f"KX{subject.upper()}"
    if vertical == "sports" and subject in {
        "mlb",
        "nba",
        "nfl",
        "ncaaf",
        "ncaamb",
        "nhl",
        "wnba",
    }:
        return f"KX{subject.upper()}"
    return None


def cohort_base_genome(scope: str) -> ForecastGenome | None:
    """Derive an isolated generation-zero genome for one exact cohort."""
    vertical, subject, market_type, axis = _scope_parts(scope)
    pilots = pilot_genomes()
    if vertical == "crypto" and subject in {"btc", "eth", "sol"}:
        seed = next(genome for genome in pilots if genome.vertical == "crypto")
        genome_vertical = "crypto"
    elif vertical == "sports" and subject == "mlb":
        seed = next(genome for genome in pilots if genome.vertical == "mlb")
        genome_vertical = subject
    else:
        return None
    if axis == "unknown":
        return None
    scope_evidence = f"exact-cohort:{digest_json({'scope': scope})}"
    genes = list(seed.genes)
    if vertical == "crypto" and market_type == "price_ladder":
        genes.extend(
            (
                Gene(
                    name="strike.selection_mode",
                    category=GeneCategory.DECISION_RULE,
                    value="rank_all_contemporaneously_listed_nearest_expiry_targets",
                    version="crypto-strike-autoresearch-v1",
                    evidence_ids=(scope_evidence,),
                ),
                Gene(
                    name="strike.selection_objective",
                    category=GeneCategory.DECISION_RULE,
                    value="fee_uncertainty_adjusted_conservative_ev",
                    version="crypto-strike-autoresearch-v1",
                    evidence_ids=(scope_evidence,),
                ),
                Gene(
                    name="strike.listed_targets_only",
                    category=GeneCategory.DECISION_RULE,
                    value=True,
                    version="crypto-strike-autoresearch-v1",
                    evidence_ids=(scope_evidence,),
                ),
                Gene(
                    name="strike.counterfactual_requires_frozen_ladder",
                    category=GeneCategory.DECISION_RULE,
                    value=True,
                    version="crypto-strike-autoresearch-v1",
                    evidence_ids=(scope_evidence,),
                ),
            )
        )
    return ForecastGenome.create(
        label=f"{scope} exact-cohort generation zero",
        vertical=genome_vertical,
        market_type=market_type,
        horizon=axis,
        generation=0,
        parent_genome_ids=(),
        genes=tuple(genes),
        created_at=seed.created_at,
        evidence_ids=tuple(sorted((*seed.evidence_ids, scope_evidence))),
    )


def _safe_scope_id(scope: str) -> str:
    return digest_json({"scope": scope})[:16]


def run_multi_cohort_campaigns(
    *,
    rows: tuple[LedgerEvidenceRow, ...],
    output_dir: Path,
    maximum_cohorts: int = 16,
    per_experiment_compute_budget: float = 5_000.0,
    deadline: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Discover, validate, budget, and run each cohort independently.

    ``deadline`` is an optional predicate returning True once the caller's run
    budget is spent. It is consulted between cohorts, so an unattended run
    stops scheduling new campaigns instead of overrunning its scheduled slot.
    Cohorts that were not reached are recorded as deferred -- never as
    completed, and never as evidence.
    """
    discovered = discover_exact_cohorts(rows)
    scheduled: list[dict[str, Any]] = []
    campaigns: list[dict[str, Any]] = []
    viable = 0
    for cohort in discovered:
        base = cohort_base_genome(cohort.scope)
        status = "ELIGIBLE"
        reason = None
        plan = None
        if cohort.scope.endswith("|unknown"):
            status = "BLOCKED_MISSING_HORIZON_PROVENANCE"
            reason = "hourly and daily crypto must remain separately gated"
        elif base is None:
            status = "NO_COMPATIBLE_GENERATION_ZERO_GENOME"
            reason = "no bounded organism template exists for this exact cohort"
        else:
            try:
                plan = build_ledger_partition_plan(cohort.rows, scope=cohort.scope)
            except AutoresearchValidationError as exc:
                status = "ACCUMULATING_PARTITION_EVIDENCE"
                reason = str(exc)
        if status == "ELIGIBLE":
            viable += 1
        scheduled.append(
            {
                "scope": cohort.scope,
                "row_count": len(cohort.rows),
                "decision_dates": cohort.decision_dates,
                "status": status,
                "reason": reason,
                "base_genome_id": base.genome_id if base else None,
                "priority_inputs": {
                    "evidence_volume": len(cohort.rows),
                    "partition_viable": plan is not None,
                    "exact_gate": True,
                    "cross_cohort_transfer": False,
                },
            }
        )

    eligible = [item for item in scheduled if item["status"] == "ELIGIBLE"]
    eligible.sort(key=lambda item: (-int(item["row_count"]), str(item["scope"])))
    selected_scopes = {str(item["scope"]) for item in eligible[:maximum_cohorts]}
    cohort_lookup = {item.scope: item for item in discovered}
    deadline_reached = False
    for item in scheduled:
        scope = str(item["scope"])
        if item["status"] != "ELIGIBLE":
            continue
        if scope not in selected_scopes:
            item["status"] = "DEFERRED_FIXED_COHORT_BUDGET"
            item["reason"] = "lower deterministic priority under maximum_cohorts"
            continue
        if deadline is not None and deadline():
            deadline_reached = True
            item["status"] = "DEFERRED_RUN_DEADLINE"
            item["reason"] = "run deadline reached before this cohort started"
            continue
        cohort = cohort_lookup[scope]
        base = cohort_base_genome(scope)
        assert base is not None
        plan = build_ledger_partition_plan(cohort.rows, scope=scope)
        created_at = max(row.settlement_received_at for row in cohort.rows) + timedelta(
            microseconds=1
        )
        campaign = run_loop1_campaign(
            rows=cohort.rows,
            plan=plan,
            base_genome=base,
            created_at=created_at,
            per_experiment_compute_budget=per_experiment_compute_budget,
        )
        cohort_dir = output_dir / "cohorts" / _safe_scope_id(scope)
        campaign_path = cohort_dir / "campaign_report.json"
        write_campaign_report(campaign, campaign_path)
        campaigns.append(
            {
                "scope": scope,
                "ticker_prefix": cohort_ticker_prefix(scope),
                "base_genome": base.to_dict(),
                "campaign": campaign,
                "campaign_path": str(campaign_path),
                "cohort_output_dir": str(cohort_dir),
            }
        )
        item["status"] = "CAMPAIGN_COMPLETED"
        item["campaign_id"] = campaign["campaign_id"]
        item["private_survivors"] = campaign["private_survivors"]
        item["external_survivors"] = campaign["external_survivors"]

    body: dict[str, Any] = {
        "schema_version": 1,
        "campaign_name": "DUMMY_AUTORESEARCH_MULTI_EXACT_COHORT_V1",
        "discovered_cohorts": len(discovered),
        "viable_cohorts": viable,
        "campaigns_completed": len(campaigns),
        "run_deadline_reached": deadline_reached,
        "cohorts_deferred_by_deadline": sum(
            1 for item in scheduled if item["status"] == "DEFERRED_RUN_DEADLINE"
        ),
        "scheduler": {
            "autonomous": True,
            "priority": "evidence_volume_then_scope",
            "maximum_cohorts": maximum_cohorts,
            "one_campaign_per_exact_cohort": True,
            "one_bounded_trial_per_eligible_lineage": True,
            "per_experiment_compute_budget": per_experiment_compute_budget,
            "private_item_feedback_exposed": False,
            "external_used_for_selection": False,
        },
        "strike_selection_law": {
            "hourly_and_daily_adjustment_enabled": True,
            "listed_targets_only": True,
            "nearest_expiry_only": True,
            "frozen_ladder_required_for_counterfactual_replay": True,
            "hourly_and_daily_share_promotion_gate": False,
            "settlement_informed_strike_selection": False,
        },
        "schedule": scheduled,
        "campaigns": campaigns,
        "automatic_negative_actions": ["reject", "quarantine", "contract", "demote"],
        "automatic_positive_promotion": False,
        "promotion_authority": "HUMAN_ONLY",
        "orders_placed": False,
        "execution_authority": False,
        "capital_authority": False,
        "performance_claim_supported": False,
    }
    body["report_id"] = digest_json(body)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "multi_cohort_report.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return body


__all__ = [
    "CohortCandidate",
    "cohort_base_genome",
    "cohort_ticker_prefix",
    "discover_exact_cohorts",
    "run_multi_cohort_campaigns",
]
