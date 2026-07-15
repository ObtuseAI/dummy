"""Canonical Phase 8 benchmark program for every internal claim family."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from dummy.world_model.models import digest_json


class BenchmarkDomain(str, Enum):
    FORECAST_QUALITY = "forecast_quality"
    MULTI_AGENT_VALUE = "multi_agent_value"
    METACOGNITIVE_QUALITY = "metacognitive_quality"
    EXECUTION_REALISM = "execution_realism"
    EVOLUTION_QUALITY = "evolution_quality"
    GOVERNANCE_QUALITY = "governance_quality"


@dataclass(frozen=True, slots=True)
class BenchmarkMetric:
    metric_id: str
    domain: BenchmarkDomain
    name: str
    empirical: bool
    required_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("benchmark metric name must be non-empty")
        required = tuple(sorted(str(item).strip() for item in self.required_evidence))
        if not required or any(not item for item in required):
            raise ValueError("benchmark metric requires evidence types")
        object.__setattr__(self, "required_evidence", required)
        if self.metric_id != digest_json(self.semantic_dict()):
            raise ValueError("benchmark metric ID mismatch")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "domain": self.domain.value,
            "name": self.name,
            "empirical": self.empirical,
            "required_evidence": list(self.required_evidence),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"metric_id": self.metric_id, **self.semantic_dict()}


_CATALOG: dict[BenchmarkDomain, tuple[str, ...]] = {
    BenchmarkDomain.FORECAST_QUALITY: (
        "brier_improvement_versus_market",
        "log_loss_improvement",
        "contested_market_advantage",
        "calibration",
        "sharpness_without_overconfidence",
    ),
    BenchmarkDomain.MULTI_AGENT_VALUE: (
        "organism_versus_incumbent_pipeline",
        "agent_ablation",
        "challenger_contribution",
        "consensus_correlation",
        "source_family_independence",
    ),
    BenchmarkDomain.METACOGNITIVE_QUALITY: (
        "difficulty_prediction",
        "knowledge_boundary_accuracy",
        "confidence_calibration",
        "abstention_value",
        "strategy_selection_value",
        "compute_allocation_efficiency",
    ),
    BenchmarkDomain.EXECUTION_REALISM: (
        "queue_model_accuracy",
        "fill_prediction",
        "fee_accuracy",
        "partial_fill_handling",
        "fill_conditioned_profitability",
    ),
    BenchmarkDomain.EVOLUTION_QUALITY: (
        "challenger_improvement",
        "transfer_across_seasons_and_regimes",
        "forward_paper_survival",
        "genome_reproducibility",
        "meta_policy_improvement",
    ),
    BenchmarkDomain.GOVERNANCE_QUALITY: (
        "no_authority_expansion",
        "no_truth_layer_mutation",
        "no_forced_coverage_contamination",
        "full_replay",
        "deterministic_kill_behavior",
        "credential_isolation",
    ),
}


def benchmark_catalog() -> tuple[BenchmarkMetric, ...]:
    metrics: list[BenchmarkMetric] = []
    for domain, names in _CATALOG.items():
        for name in names:
            empirical = domain is not BenchmarkDomain.GOVERNANCE_QUALITY
            evidence = (
                ("point_in_time_held_out", "event_cluster_statistics")
                if empirical
                else ("deterministic_governance_audit", "protected_surface_manifest")
            )
            semantic = {
                "schema_version": 1,
                "domain": domain.value,
                "name": name,
                "empirical": empirical,
                "required_evidence": sorted(evidence),
            }
            metrics.append(
                BenchmarkMetric(
                    metric_id=digest_json(semantic),
                    domain=domain,
                    name=name,
                    empirical=empirical,
                    required_evidence=evidence,
                )
            )
    return tuple(sorted(metrics, key=lambda item: item.metric_id))


def benchmark_catalog_manifest() -> dict[str, Any]:
    metrics = benchmark_catalog()
    body: dict[str, Any] = {
        "schema_version": 1,
        "phase": 8,
        "metric_count": len(metrics),
        "domains": {
            domain.value: sum(item.domain is domain for item in metrics)
            for domain in BenchmarkDomain
        },
        "metrics": [item.to_dict() for item in metrics],
        "performance_claim_supported": False,
        "execution_authority": False,
    }
    body["catalog_id"] = digest_json(body)
    return body


__all__ = [
    "BenchmarkDomain",
    "BenchmarkMetric",
    "benchmark_catalog",
    "benchmark_catalog_manifest",
]
