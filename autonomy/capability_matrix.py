"""Fail-closed research and live-source capability reporting.

The matrix does not change fusion or shadow collection.  It makes the proof
boundary explicit: default-fusing sources may continue to emit and be graded,
but live-canary authority is denied until every active exact scope has enough
receipt-bounded evidence, an earned exact-scope weight, and no decisive
negative contested record.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from autonomy.taxonomy import grading_scope

MIN_EXACT_SCOPE_SETTLED = 20
MIN_EXACT_SCOPE_CONTESTED = 20
MIN_EXACT_SCOPE_EVENT_CLUSTERS = 10


def build_live_source_capability_matrix(
    signals_by_ticker: Mapping[str, Sequence[Mapping[str, Any]]],
    sources_by_scope: Mapping[str, Mapping[str, Any]],
    weights: Mapping[str, float],
    *,
    source_evidence_mode: str,
    required_evidence_mode: str,
) -> dict[str, Any]:
    """Grade default-fusing exact scopes without suppressing research tape."""
    emissions: dict[str, dict[str, int]] = {}
    for ticker, rows in signals_by_ticker.items():
        latest: dict[str, Mapping[str, Any]] = {}
        for row in rows:
            source = str(row.get("source") or "")
            if source:
                latest[source] = row
        for source, row in latest.items():
            features = row.get("features") or {}
            scope = grading_scope(source, str(ticker), features)
            counts = emissions.setdefault(
                scope, {"default_fusion": 0, "challenger_only": 0},
            )
            key = (
                "challenger_only"
                if bool(features.get("challenger_only"))
                else "default_fusion"
            )
            counts[key] += 1

    scope_keys = sorted(set(sources_by_scope) | set(emissions))
    scopes: dict[str, dict[str, Any]] = {}
    blocking_scopes: list[str] = []
    required_scopes: list[str] = []
    mode_is_authoritative = source_evidence_mode == required_evidence_mode
    for scope in scope_keys:
        summary = dict(sources_by_scope.get(scope) or {})
        counts = emissions.get(
            scope, {"default_fusion": 0, "challenger_only": 0},
        )
        source = str(scope).split("|", 1)[0]
        default_fusion_member = counts["default_fusion"] > 0
        requires_proof = default_fusion_member and source != "market_prior"
        if requires_proof:
            required_scopes.append(scope)
        n = int(summary.get("n") or 0)
        contested_n = int(summary.get("contested_n") or 0)
        clusters = int(summary.get("contested_event_clusters") or 0)
        ci = summary.get("contested_mean_brier_edge_ci95") or {}
        ci_upper = ci.get("upper")
        weight_key = f"scope:{scope}"
        reasons: list[str] = []
        if requires_proof and not mode_is_authoritative:
            reasons.append("source_evidence_mode_not_receipt_bounded_live_only")
        if requires_proof and n < MIN_EXACT_SCOPE_SETTLED:
            reasons.append(
                f"settled_exact_scope_sample_{n}_below_{MIN_EXACT_SCOPE_SETTLED}"
            )
        if requires_proof and contested_n < MIN_EXACT_SCOPE_CONTESTED:
            reasons.append(
                f"contested_exact_scope_sample_{contested_n}_below_"
                f"{MIN_EXACT_SCOPE_CONTESTED}"
            )
        if requires_proof and clusters < MIN_EXACT_SCOPE_EVENT_CLUSTERS:
            reasons.append(
                f"contested_event_clusters_{clusters}_below_"
                f"{MIN_EXACT_SCOPE_EVENT_CLUSTERS}"
            )
        if requires_proof and weight_key not in weights:
            reasons.append("earned_exact_scope_weight_missing")
        if requires_proof and ci_upper is not None and float(ci_upper) < 0.0:
            reasons.append("decisively_negative_contested_brier_edge")
        capable = not reasons
        if requires_proof and not capable:
            blocking_scopes.append(scope)
        scopes[scope] = {
            "source": source,
            "default_fusion_member": default_fusion_member,
            "challenger_only": not default_fusion_member,
            "requires_live_capability_proof": requires_proof,
            "live_canary_capable": capable,
            "blocking_reasons": reasons,
            "live_settled_observations": n,
            "live_contested_observations": contested_n,
            "live_contested_event_clusters": clusters,
            "contested_brier_edge_ci95": ci,
            "exact_scope_weight_key": weight_key,
            "exact_scope_weight_present": weight_key in weights,
            "emissions": counts,
        }

    global_blockers: list[str] = []
    if not mode_is_authoritative:
        global_blockers.append("source evidence is not receipt-bounded live-only")
    if not required_scopes:
        global_blockers.append("no default-fusing non-market exact scope has evidence")
    if blocking_scopes:
        global_blockers.append(
            f"{len(blocking_scopes)} default-fusing exact scopes lack capability proof"
        )
    return {
        "schema_version": 1,
        "matrix_name": "LIVE_SOURCE_CAPABILITY_MATRIX",
        "source_evidence_mode": source_evidence_mode,
        "required_evidence_mode": required_evidence_mode,
        "ready_for_live_canary": not global_blockers,
        "global_blockers": global_blockers,
        "required_default_fusion_scopes": required_scopes,
        "blocking_scopes": blocking_scopes,
        "scopes": scopes,
        "inline_negative_scope_check": (
            "fresh receipt-bounded exact-scope CI; no no-edge artifact dependency"
        ),
        "enforcement_surface": "live_canary_only",
        "shadow_collection_allowed": True,
        "challenger_grading_allowed": True,
        "fusion_mutated": False,
        "promotion_authority": False,
        "execution_authority": False,
        "capital_authority": False,
    }


def build_research_capability_matrix(
    *,
    forecast: Mapping[str, Any],
    execution: Mapping[str, Any],
    evolution: Mapping[str, Any],
) -> dict[str, Any]:
    """Report what the current improvement loop can actually prove."""
    experiment = execution.get("experiment") or {}
    separation = experiment.get("evidence_separation") or {}
    lifecycle = str(experiment.get("lifecycle_state") or "UNREGISTERED")
    candidate_state = str(experiment.get("candidate_state") or "UNKNOWN")
    closed = bool(experiment.get("closed"))
    retirement_consistent = not (
        lifecycle.startswith("CLOSED_RETIRED") and candidate_state != "RETIRED"
    )
    return {
        "schema_version": 1,
        "matrix_name": "RESEARCH_IMPROVEMENT_CAPABILITY_MATRIX",
        "overall_status": (
            "EVIDENCE_DISCIPLINED_RESEARCH_ONLY"
            if separation.get("verified") and retirement_consistent
            else "INCOMPLETE_PROOF_SURFACE"
        ),
        "capabilities": {
            "bounded_hypothesis_generation": {
                "implemented": bool(
                    (evolution.get("population") or {}).get("candidates_generated")
                ),
                "evidence": "evolution_lab.population",
            },
            "experiment_registration": {
                "implemented": bool(experiment.get("protocol_sha256")),
                "state": experiment.get("registration_state"),
                "protocol_sha256": experiment.get("protocol_sha256"),
            },
            "train_validation_holdout_separation": {
                "implemented": bool(separation.get("verified")),
                "cluster_intersections": separation.get("cluster_intersections"),
                "receipt_bounded": separation.get(
                    "strict_receipt_bounded_outcome_truth", False
                ),
            },
            "experiment_closure": {
                "implemented": closed,
                "lifecycle_state": lifecycle,
                "candidate_state": candidate_state,
            },
            "failure_retirement": {
                "implemented": retirement_consistent,
                "automatic_scope": "research_candidate_only",
            },
            "multiple_testing_control": {
                "implemented": bool(experiment.get("multiple_testing_control")),
                "method": experiment.get("multiple_testing_control"),
                "limitation": (
                    "isolates one selected execution policy; does not authorize "
                    "production or replace domain-specific FDR"
                ),
            },
            "forward_rollback": {
                "implemented": True,
                "rotation": (
                    (evolution.get("active_research_candidate") or {}).get(
                        "rotation_reason"
                    )
                ),
                "scope": "research epoch only",
            },
            "positive_promotion": {
                "implemented": False,
                "reason": "simulation evidence remains challenger-only",
            },
        },
        "forecast_shadow_experiment_eligible": bool(
            forecast.get("eligible_for_shadow_experiment")
        ),
        "execution_shadow_experiment_eligible": bool(
            execution.get("eligible_for_shadow_experiment")
        ),
        "shadow_collection_allowed": True,
        "promotion_authority": False,
        "execution_authority": False,
        "capital_authority": False,
    }
