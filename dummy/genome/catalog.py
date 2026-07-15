"""Canonical generation-zero genomes for the two vNext pilot organisms."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dummy.organisms.templates import phase3_template_manifest
from dummy.world_model.models import digest_json

from .schema import ForecastGenome, Gene, GeneCategory


CATALOG_CREATED_AT = datetime(2026, 7, 15, tzinfo=timezone.utc)


def _genes(template: dict[str, Any], evidence_id: str) -> tuple[Gene, ...]:
    contracts = template["contracts"]
    values = (
        (
            "organism.agent_composition",
            GeneCategory.AGENT_COMPOSITION,
            template["dependency_order"],
        ),
        (
            "organism.source_selection",
            GeneCategory.SOURCE_SELECTION,
            sorted({item["source_family"] for item in contracts}),
        ),
        (
            "synthesis.family_caps",
            GeneCategory.FORECAST_COMBINATION,
            {
                "market_prior_floor": 0.50,
                "non_market_family_cap": 0.35,
                "uncalibrated_advisory_cap": 0.15,
            },
        ),
        (
            "synthesis.market_prior_weight",
            GeneCategory.MARKET_PRIOR_WEIGHT,
            0.50,
        ),
        (
            "uncertainty.disagreement_model",
            GeneCategory.UNCERTAINTY_MODEL,
            "base_uncertainty_plus_weighted_dispersion",
        ),
        (
            "adversarial.sequence",
            GeneCategory.ADVERSARIAL_SEQUENCE,
            ["contrarian", "adversary", "shadow", "synthesizer"],
        ),
        ("replay.depth", GeneCategory.REPLAY_DEPTH, 5),
        ("simulation.path_budget", GeneCategory.SIMULATION_BUDGET, 0),
        ("abstention.epistemic_threshold", GeneCategory.ABSTENTION_THRESHOLD, 0.22),
        (
            "decision.rule",
            GeneCategory.DECISION_RULE,
            "positive_edge_after_fees_spread_uncertainty_and_guards",
        ),
        (
            "calibration.policy",
            GeneCategory.CALIBRATION_POLICY,
            sorted({item["calibration_identity"] for item in contracts}),
        ),
        (
            "metacognition.policy",
            GeneCategory.METACOGNITIVE_POLICY,
            "shadow_only_except_safety_contraction",
        ),
        (
            "mutation.policy",
            GeneCategory.MUTATION_POLICY,
            "proposal_only_external_evaluator_human_promotion",
        ),
    )
    return tuple(
        Gene(
            name=name,
            category=category,
            value=value,
            version="phase6-pilot-v1",
            evidence_ids=(evidence_id,),
        )
        for name, category, value in values
    )


def pilot_genomes() -> tuple[ForecastGenome, ...]:
    genomes = []
    for template in phase3_template_manifest()["templates"]:
        evidence_id = digest_json(template)
        genomes.append(
            ForecastGenome.create(
                label=f"{template['template_id']} generation zero",
                vertical=str(template["vertical"]),
                market_type=str(template["market_type"]),
                horizon=str(template["clock_domain"]),
                generation=0,
                parent_genome_ids=(),
                genes=_genes(template, evidence_id),
                created_at=CATALOG_CREATED_AT,
                evidence_ids=(evidence_id, str(template["template_id"])),
            )
        )
    return tuple(sorted(genomes, key=lambda item: item.genome_id))


def genome_catalog_manifest() -> dict[str, Any]:
    genomes = pilot_genomes()
    body: dict[str, Any] = {
        "schema_version": 1,
        "phase": 6,
        "status": "GENERATION_ZERO_ARCHITECTURES_ONLY",
        "genome_count": len(genomes),
        "genomes": [item.to_dict() for item in genomes],
        "performance_claim_supported": False,
        "runtime_applied": False,
        "execution_authority": False,
        "promotion_authority": "HUMAN_ONLY",
    }
    body["catalog_id"] = digest_json(body)
    return body


__all__ = ["genome_catalog_manifest", "pilot_genomes"]
