"""Build the honest checked-in Phase 7 observatory projection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from dummy.constitution import protected_manifest_digest
from dummy.observatory.models import (
    EvidenceClaim,
    ObservatoryPanel,
    ObservatorySnapshot,
    PanelProjection,
)
from dummy.world_model.models import digest_json


PHASE7_SNAPSHOT_TIME = datetime(2026, 7, 15, tzinfo=timezone.utc)


def _claim(
    label: str,
    value: Any,
    status: str,
    evidence_ids: tuple[str, ...],
    *limitations: str,
) -> EvidenceClaim:
    semantic = {
        "schema_version": 1,
        "label": label,
        "value": value,
        "status": status,
        "evidence_ids": sorted(evidence_ids),
        "limitations": sorted(limitations),
    }
    return EvidenceClaim(
        claim_id=digest_json(semantic),
        label=label,
        value=value,
        status=status,
        evidence_ids=evidence_ids,
        limitations=tuple(limitations),
    )


def build_phase7_observatory_snapshot(
    *,
    homeostasis_manifest: Mapping[str, Any],
    arena_catalog_manifest: Mapping[str, Any],
    arena_report: Mapping[str, Any],
    genome_catalog_manifest: Mapping[str, Any],
    evolution_evidence: Mapping[str, Any],
) -> ObservatorySnapshot:
    source_artifacts = {
        "baseline": "docs/VNEXT_PHASE0_BASELINE.json",
        "world_model_ablation": "docs/VNEXT_PHASE4_WORLD_STATE_ABLATION.json",
        "phase5_evidence": "docs/VNEXT_PHASE5_METACOGNITION_CALIBRATION.json",
        "genomes": "docs/VNEXT_PHASE6_GENOME_CATALOG.json",
        "evolution": "docs/VNEXT_PHASE6_EVOLUTION_EVIDENCE.json",
        "homeostasis": "docs/VNEXT_PHASE7_HOMEOSTASIS_POLICY.json",
        "arenas": "docs/VNEXT_PHASE7_ARENA_REPRODUCIBILITY.json",
        "constitution": "docs/VNEXT_PROTECTED_SURFACES.json",
    }
    panels = (
        PanelProjection(
            ObservatoryPanel.COMMAND_CENTER,
            (
                _claim("runtime_health", "NOT_OBSERVED", "UNKNOWN", ("phase7-static-audit",), "no live vNext telemetry is checked in"),
                _claim("execution_seal", True, "VERIFIED", (protected_manifest_digest(),)),
                _claim("active_vnext_organisms", 0, "POINT_IN_TIME", ("phase7-static-audit",)),
            ),
        ),
        PanelProjection(
            ObservatoryPanel.FORECAST_ORGANISMS,
            (
                _claim("generation_zero_genomes", genome_catalog_manifest["genome_count"], "CATALOGED", (str(genome_catalog_manifest["catalog_id"]),)),
                _claim("running_organisms", 0, "NOT_OBSERVED", ("phase7-static-audit",), "dashboard snapshot is not a runtime control plane"),
            ),
        ),
        PanelProjection(
            ObservatoryPanel.WORLD_MODELS,
            (
                _claim("state_contract", "VERSIONED_CAUSAL", "VERIFIED", ("docs/VNEXT_PHASE4_WORLD_MODELS.md",)),
                _claim("transfer_claim", False, "INSUFFICIENT_SETTLED_EVIDENCE", ("docs/VNEXT_PHASE4_REGIME_TRANSFER.json",)),
            ),
        ),
        PanelProjection(
            ObservatoryPanel.CALIBRATION,
            (
                _claim("metacognitive_calibration_claim", False, "INSUFFICIENT_SETTLED_EVIDENCE", ("docs/VNEXT_PHASE5_METACOGNITION_CALIBRATION.json",)),
                _claim("evolution_candidate_count", evolution_evidence["candidate_count"], str(evolution_evidence["status"]), (str(evolution_evidence["family_report_id"]),)),
            ),
        ),
        PanelProjection(
            ObservatoryPanel.EXECUTION_TRUTH,
            (
                _claim("execution_authority", False, "SEALED", (protected_manifest_digest(),)),
                _claim("simulated_fill_is_realized_pnl", False, "VERIFIED", ("docs/VNEXT_PHASE6_MEMORY_POLICY.json",)),
                _claim("witnessed_vnext_fills", 0, "NOT_OBSERVED", ("phase7-static-audit",)),
            ),
        ),
        PanelProjection(
            ObservatoryPanel.EVOLUTION,
            (
                _claim("registered_genomes", genome_catalog_manifest["genome_count"], str(genome_catalog_manifest["status"]), (str(genome_catalog_manifest["catalog_id"]),)),
                _claim("evaluated_candidates", evolution_evidence["candidate_count"], str(evolution_evidence["status"]), (str(evolution_evidence["family_report_id"]),)),
                _claim("automatic_promotion", False, "PROHIBITED", (protected_manifest_digest(),)),
            ),
        ),
        PanelProjection(
            ObservatoryPanel.HOMEOSTASIS,
            (
                _claim("monitored_variables", homeostasis_manifest["variable_count"], "POLICY_DEFINED", (str(homeostasis_manifest["manifest_id"]),)),
                _claim("runtime_readings", 0, "NOT_OBSERVED", (str(homeostasis_manifest["manifest_id"]),), "unknown readings fail closed"),
                _claim("authority_expansion", False, "PROHIBITED", (str(homeostasis_manifest["manifest_id"]),)),
            ),
        ),
        PanelProjection(
            ObservatoryPanel.CONSTITUTION,
            (
                _claim("protected_manifest_digest", protected_manifest_digest(), "VERIFIED", (protected_manifest_digest(),)),
                _claim("arena_scenarios", arena_catalog_manifest["scenario_count"], "CATALOGED", (str(arena_catalog_manifest["catalog_id"]),)),
                _claim("arena_replay", arena_report["passing_count"], str(arena_report["status"]), (str(arena_report["report_id"]),), "mechanical fixtures do not establish empirical resilience"),
            ),
        ),
    )
    semantic = {
        "schema_version": 1,
        "phase": 7,
        "generated_at": "2026-07-15T00:00:00Z",
        "panels": [
            item.to_dict() for item in sorted(panels, key=lambda item: item.panel.value)
        ],
        "source_artifacts": source_artifacts,
        "telemetry_status": "POINT_IN_TIME_SNAPSHOT_NO_LIVE_TELEMETRY",
        "authority": "OBSERVE",
        "read_only": True,
        "write_actions": [],
        "execution_authority": False,
    }
    return ObservatorySnapshot(
        snapshot_id=digest_json(semantic),
        generated_at=PHASE7_SNAPSHOT_TIME,
        panels=panels,
        source_artifacts=source_artifacts,
        telemetry_status="POINT_IN_TIME_SNAPSHOT_NO_LIVE_TELEMETRY",
    )


__all__ = ["PHASE7_SNAPSHOT_TIME", "build_phase7_observatory_snapshot"]
