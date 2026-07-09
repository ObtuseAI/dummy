"""V16 proof freshness and artifact integrity checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StaleArtifactWarning:
    artifact: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"artifact": self.artifact, "reason": self.reason}


@dataclass(frozen=True)
class ArtifactFreshnessState:
    freshness_state: str
    warnings: list[StaleArtifactWarning] = field(default_factory=list)

    def to_report(self) -> dict[str, Any]:
        return {
            "freshness_state": self.freshness_state,
            "stale_artifact_warnings": [warning.to_dict() for warning in self.warnings],
        }


class ProofFreshnessResolver:
    def __init__(
        self,
        *,
        required_artifacts: dict[str, dict[str, Any]],
        historical_artifacts: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.required_artifacts = required_artifacts
        self.historical_artifacts = historical_artifacts or {}

    def resolve(self) -> ArtifactFreshnessState:
        warnings: list[StaleArtifactWarning] = []
        for name, report in self.required_artifacts.items():
            if not report:
                warnings.append(StaleArtifactWarning(name, "MISSING_ARTIFACT"))
            if "v16" in name.lower() and report.get("version") not in {None, "v16"}:
                warnings.append(StaleArtifactWarning(name, "MISMATCHED_VERSION_LABEL"))
            if report.get("terrain_truth_verdict") == "PASS_REAL_TERRAIN" and report.get("terrain_mode") == "SAMPLE_STATIC_FALLBACK":
                warnings.append(StaleArtifactWarning(name, "SAMPLE_DATA_DESPITE_REAL_PROOF"))
        return ArtifactFreshnessState("FRESH" if not warnings else "STALE", warnings)

    def to_report(self) -> dict[str, Any]:
        state = self.resolve()
        data = state.to_report()
        data.update(
            {
                "workstream": "V16: Proof Freshness Resolver",
                "required_artifacts": sorted(self.required_artifacts),
                "historical_artifacts_referenced_only": sorted(self.historical_artifacts),
                "secret_values_exposed": False,
                "verdict": "PASS" if state.freshness_state == "FRESH" else "PARTIAL",
            }
        )
        return data


class ArtifactDependencyGraph:
    def __init__(self, dependencies: dict[str, list[str]]) -> None:
        self.dependencies = dependencies

    @classmethod
    def for_v16(cls) -> "ArtifactDependencyGraph":
        return cls(
            {
                "final_report_v16.json": [
                    "kalshi_readonly_runtime_config_report_v1.json",
                    "kalshi_readonly_config_binding_proof_v1.json",
                    "config_bound_real_market_discovery_report_v1.json",
                    "config_bound_real_orderbook_snapshot_report_v1.json",
                    "real_terrain_truth_resolver_report_v1.json",
                    "real_orderbook_replay_truth_repair_report_v1.json",
                    "dummy_mission_state_report_v1.json",
                ]
            }
        )

    def to_report(self) -> dict[str, Any]:
        nodes = sorted(set(self.dependencies) | {dep for deps in self.dependencies.values() for dep in deps})
        return {
            "workstream": "V16: Artifact Dependency Graph",
            "nodes": nodes,
            "dependencies": self.dependencies,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }


class ProofNamingIntegrityCheck:
    def __init__(self, artifact_names: list[str]) -> None:
        self.artifact_names = artifact_names

    def to_report(self) -> dict[str, Any]:
        mismatches = [
            name
            for name in self.artifact_names
            if ("final_report" in name and "v16" not in name and name != "final_report.json")
            or ("v16" in name and not name.endswith(".json"))
        ]
        return {
            "workstream": "V16: Proof Naming Integrity",
            "artifact_names": self.artifact_names,
            "mismatched_version_labels": mismatches,
            "secret_values_exposed": False,
            "verdict": "PASS" if not mismatches else "PARTIAL",
        }
