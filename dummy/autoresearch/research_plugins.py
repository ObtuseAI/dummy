"""Code-owned plugin adapters for Dummy's three research subsystems."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from dummy.world_model.models import digest_json

from .control_models import (
    EvidenceSnapshot,
    ResearchBudgetPolicy,
    ResearchDefinition,
    ResearchKind,
)
from .models import AutoresearchValidationError
from .negative_controls import CONTROL_IDS


INTELLIGENCE_PLUGIN_ID = "dummy.intelligence_lab"
INTELLIGENCE_PLUGIN_VERSION = "intelligence-control-adapter-v1"
EVOLUTION_PLUGIN_ID = "autonomy.evolution_lab"
EVOLUTION_PLUGIN_VERSION = "evolution-control-adapter-v1"

_INTELLIGENCE_INTERVENTIONS = frozenset(
    {
        "preregistered_abstraction_cognitive_pipeline",
        "preregistered_analogy_cognitive_pipeline",
        "preregistered_constraint_inversion_cognitive_pipeline",
        "preregistered_constraint_relaxation_cognitive_pipeline",
        "preregistered_counterfactual_reasoning_cognitive_pipeline",
        "preregistered_cross_domain_transfer_cognitive_pipeline",
        "preregistered_first_principles_reconstruction_cognitive_pipeline",
        "preregistered_inversion_cognitive_pipeline",
        "preregistered_morphological_search_cognitive_pipeline",
        "preregistered_recombination_cognitive_pipeline",
    }
)


def intelligence_definition_from_protocol(
    protocol: Mapping[str, Any],
    *,
    seed: int = 0,
    budget: ResearchBudgetPolicy | None = None,
) -> ResearchDefinition:
    """Adapt a generated Intelligence Lab protocol without executing prose."""
    if bool(protocol.get("candidate_controls_evaluator")):
        raise AutoresearchValidationError(
            "an intelligence candidate cannot control its evaluator"
        )
    authority = str(protocol.get("authority") or "SIMULATE_MAXIMUM")
    if authority != "SIMULATE_MAXIMUM":
        raise AutoresearchValidationError(
            "intelligence protocols are limited to protected simulation"
        )
    experiment_id = str(protocol.get("experiment_id") or "").strip()
    hypothesis_id = str(protocol.get("hypothesis_id") or "").strip()
    intervention = str(protocol.get("intervention") or "").strip()
    if not experiment_id or not hypothesis_id or not intervention:
        raise AutoresearchValidationError("intelligence protocol is incomplete")
    stable_protocol = {
        "domain_id": str(protocol.get("domain_id") or "").strip(),
        "intervention": intervention,
        "control": str(protocol.get("control") or "").strip(),
        "private_metrics": sorted(protocol.get("private_metrics") or ()),
        "required_partitions": sorted(protocol.get("required_partitions") or ()),
        "replication_seed_count": int(protocol.get("replication_seed_count") or 0),
    }
    method_id = digest_json(stable_protocol)
    return ResearchDefinition.create(
        plugin_id=INTELLIGENCE_PLUGIN_ID,
        plugin_version=INTELLIGENCE_PLUGIN_VERSION,
        kind=ResearchKind.INTELLIGENCE_PROTOCOL,
        hypothesis_id=f"intelligence-method:{method_id}",
        candidate_id=f"intelligence-candidate:{method_id}",
        evaluator_id="dummy.protected-cognitive-evaluator-v1",
        parameters={
            "protocol": stable_protocol,
            "registered_intervention": intervention in _INTELLIGENCE_INTERVENTIONS,
            "source_contract_type": "ExperimentProtocol",
        },
        required_control_ids=CONTROL_IDS,
        seed=seed,
        budget=budget or ResearchBudgetPolicy(maximum_wall_seconds=10),
    )


def intelligence_evidence_snapshot(
    *,
    multi_cohort_report: Mapping[str, Any],
    forward_report: Mapping[str, Any],
    ignition_report: Mapping[str, Any],
    captured_at: datetime,
) -> EvidenceSnapshot:
    def source_id(report: Mapping[str, Any], label: str) -> str:
        return str(
            report.get("report_id")
            or report.get("campaign_id")
            or digest_json({"label": label, "report": dict(report)})
        )

    source_ids = (
        source_id(multi_cohort_report, "multi-cohort"),
        source_id(forward_report, "forward"),
        source_id(ignition_report, "ignition"),
    )
    payload = {
        "multi_cohort": {
            "report_id": source_ids[0],
            "discovered_cohorts": int(
                multi_cohort_report.get("discovered_cohorts") or 0
            ),
            "campaigns_completed": int(
                multi_cohort_report.get("campaigns_completed") or 0
            ),
            "run_deadline_reached": bool(
                multi_cohort_report.get("run_deadline_reached")
            ),
        },
        "forward": {
            "report_id": source_ids[1],
            "settlements": int(
                forward_report.get("forward_paper_candidate_settlements") or 0
            ),
            "event_clusters": int(forward_report.get("event_clusters") or 0),
            "verified_settled_fills": int(
                forward_report.get("verified_settled_fills") or 0
            ),
        },
        "ignition": {
            "report_id": source_ids[2],
            "highest_supported_level": int(
                ignition_report.get(
                    "highest_supported_recursive_improvement_level"
                )
                or 0
            ),
        },
        "execution_authority": False,
        "capital_authority": False,
        "automatic_promotion": False,
    }
    return EvidenceSnapshot.create(
        domain_id="dummy.forecasting",
        captured_at=captured_at,
        source_ids=source_ids,
        source_family_ids=(
            "autoresearch-campaign",
            "forward-paper",
            "ignition-evidence",
        ),
        payload=payload,
        point_in_time_verified=True,
        settlement_verified=bool(payload["forward"]["settlements"] == 0)
        or bool(payload["forward"]["verified_settled_fills"]),
    )


def evolution_definition(
    *,
    evidence_fingerprint: str,
    candidate_id: str,
    population_size: int = 96,
    bootstrap_simulations: int = 1_000,
    seed: int = 0,
    budget: ResearchBudgetPolicy | None = None,
) -> ResearchDefinition:
    if not 8 <= int(population_size) <= 256:
        raise AutoresearchValidationError("evolution population is out of bounds")
    if not 100 <= int(bootstrap_simulations) <= 10_000:
        raise AutoresearchValidationError(
            "evolution bootstrap simulations are out of bounds"
        )
    return ResearchDefinition.create(
        plugin_id=EVOLUTION_PLUGIN_ID,
        plugin_version=EVOLUTION_PLUGIN_VERSION,
        kind=ResearchKind.EVOLUTION_GENERATION,
        hypothesis_id=f"bounded-evolution:{evidence_fingerprint}",
        candidate_id=candidate_id,
        evaluator_id="dummy.protected-evolution-evaluator-v1",
        parameters={
            "population_size": int(population_size),
            "bootstrap_simulations": int(bootstrap_simulations),
            "evidence_fingerprint": str(evidence_fingerprint),
        },
        required_control_ids=CONTROL_IDS,
        seed=seed,
        budget=budget or ResearchBudgetPolicy(maximum_wall_seconds=60),
    )


def evolution_evidence_snapshot(
    *,
    rows: Sequence[Mapping[str, Any]],
    captured_at: datetime,
    previous_report: Mapping[str, Any] | None = None,
) -> EvidenceSnapshot:
    normalized_rows = [dict(item) for item in rows]
    source_ids = tuple(
        sorted(
            {
                str(item.get("evidence_id") or item.get("ticker") or "").strip()
                for item in normalized_rows
            }
            - {""}
        )
    )
    if not source_ids:
        source_ids = (digest_json({"rows": normalized_rows}),)
    return EvidenceSnapshot.create(
        domain_id="dummy.forecasting.evolution",
        captured_at=captured_at,
        source_ids=source_ids,
        source_family_ids=("settled-ledger-replay",),
        payload={
            "rows": normalized_rows,
            "previous_report": dict(previous_report or {}),
            "execution_authority": False,
            "capital_authority": False,
        },
        point_in_time_verified=all(
            bool(item.get("point_in_time_verified", True))
            for item in normalized_rows
        ),
        settlement_verified=all(
            bool(item.get("settlement_verified", True))
            for item in normalized_rows
        ),
    )


def plugin_manifest() -> dict[str, Any]:
    body = {
        "schema_version": 1,
        "plugins": [
            {
                "plugin_id": INTELLIGENCE_PLUGIN_ID,
                "version": INTELLIGENCE_PLUGIN_VERSION,
                "kinds": [ResearchKind.INTELLIGENCE_PROTOCOL.value],
            },
            {
                "plugin_id": EVOLUTION_PLUGIN_ID,
                "version": EVOLUTION_PLUGIN_VERSION,
                "kinds": [ResearchKind.EVOLUTION_GENERATION.value],
            },
        ],
        "dynamic_plugin_loading": False,
        "arbitrary_commands": False,
        "network_access": False,
        "credential_access": False,
        "source_edit_applied": False,
        "automatic_promotion": False,
        "execution_authority": False,
        "capital_authority": False,
    }
    body["manifest_id"] = digest_json(body)
    return body


__all__ = [
    "EVOLUTION_PLUGIN_ID",
    "EVOLUTION_PLUGIN_VERSION",
    "INTELLIGENCE_PLUGIN_ID",
    "INTELLIGENCE_PLUGIN_VERSION",
    "evolution_definition",
    "evolution_evidence_snapshot",
    "intelligence_definition_from_protocol",
    "intelligence_evidence_snapshot",
    "plugin_manifest",
]
