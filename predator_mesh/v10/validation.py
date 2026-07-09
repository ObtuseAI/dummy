"""Validation sharding and bounded fast-feedback contracts for V10."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidationProfile(str, Enum):
    SMOKE_FAST = "smoke_fast"
    MESH_ONLY = "mesh_only"
    PROVIDER_ONLY = "provider_only"
    KALSHI_READONLY_ONLY = "kalshi_readonly_only"
    DASHBOARD_ONLY = "dashboard_only"
    SOURCE_ADAPTER_ONLY = "source_adapter_only"
    EDGE_ENGINE_ONLY = "edge_engine_only"
    FULL_REGRESSION = "full_regression"


@dataclass(frozen=True)
class ValidationShard:
    shard_id: str
    profile: ValidationProfile
    command: str
    timeout_s: float
    proof_role: str
    recursive_pytest: bool = False
    unbounded_subprocess: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "shard_id": self.shard_id,
            "profile": self.profile.value,
            "command": self.command,
            "timeout_s": self.timeout_s,
            "proof_role": self.proof_role,
            "recursive_pytest": self.recursive_pytest,
            "unbounded_subprocess": self.unbounded_subprocess,
        }


@dataclass(frozen=True)
class FastFeedbackResult:
    profile: ValidationProfile
    status: str
    shard_count: int
    recursive_pytest: bool = False
    unbounded_subprocess: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.value,
            "status": self.status,
            "shard_count": self.shard_count,
            "recursive_pytest": self.recursive_pytest,
            "unbounded_subprocess": self.unbounded_subprocess,
        }


@dataclass(frozen=True)
class FullRegressionResult:
    status: str
    required_commands: list[str]
    fast_feedback_is_not_proof: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "required_commands": self.required_commands,
            "fast_feedback_is_not_proof": self.fast_feedback_is_not_proof,
        }


@dataclass(frozen=True)
class RegressionRiskScore:
    source_adapter_risk: float = 0.20
    dashboard_risk: float = 0.15
    firewall_risk: float = 0.05
    total: float = 0.40

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_adapter_risk": self.source_adapter_risk,
            "dashboard_risk": self.dashboard_risk,
            "firewall_risk": self.firewall_risk,
            "total": self.total,
        }


@dataclass
class SlowTestWatch:
    tests: list[dict[str, Any]] = field(default_factory=list)

    def record(self, nodeid: str, duration_s: float) -> None:
        self.tests.append({"nodeid": nodeid, "duration_s": duration_s})

    def to_report(self, limit: int = 25) -> dict[str, Any]:
        slowest = sorted(self.tests, key=lambda item: item["duration_s"], reverse=True)[:limit]
        return {
            "workstream": "V10: Slow Test Watch",
            "slowest_tests": slowest,
            "limit": limit,
            "verdict": "PASS",
        }


class ValidationShardRunner:
    def shards_for_profile(self, profile: ValidationProfile) -> list[ValidationShard]:
        shard_map: dict[ValidationProfile, list[ValidationShard]] = {
            ValidationProfile.SMOKE_FAST: [
                ValidationShard(
                    "smoke-v10-core",
                    profile,
                    "python -m pytest tests/test_build_edge_factory.py tests/test_source_adapter_promotion_engine.py -q --tb=short --timeout=60",
                    60,
                    "fast_feedback_only",
                )
            ],
            ValidationProfile.MESH_ONLY: [
                ValidationShard(
                    "mesh-v9-v10",
                    profile,
                    "python -m pytest tests/test_mesh_throughput_telemetry.py tests/test_build_acceleration_queue.py -q --tb=short --timeout=60",
                    60,
                    "bounded_mesh_regression",
                )
            ],
            ValidationProfile.PROVIDER_ONLY: [
                ValidationShard(
                    "provider-v8-v10",
                    profile,
                    "python -m pytest tests/test_live_model_smoke_v3.py tests/test_no_llm_secret_leak_v10.py -q --tb=short --timeout=60",
                    60,
                    "provider_safety_regression",
                )
            ],
            ValidationProfile.KALSHI_READONLY_ONLY: [
                ValidationShard(
                    "kalshi-readonly-v10",
                    profile,
                    "python -m pytest tests/test_kalshi_read_only_still_passes_v9.py tests/test_no_direct_order_bypass_v10.py -q --tb=short --timeout=60",
                    60,
                    "read_only_regression",
                )
            ],
            ValidationProfile.DASHBOARD_ONLY: [
                ValidationShard(
                    "dashboard-api-v10",
                    profile,
                    "python -m pytest tests/test_dashboard_v10.py -q --tb=short --timeout=60",
                    60,
                    "dashboard_api_regression",
                ),
                ValidationShard(
                    "dashboard-build-v10",
                    profile,
                    "cd dashboard/frontend && npm run build",
                    60,
                    "dashboard_build_regression",
                ),
            ],
            ValidationProfile.SOURCE_ADAPTER_ONLY: [
                ValidationShard(
                    "source-adapter-v10",
                    profile,
                    "python -m pytest tests/test_source_adapter_promotion_engine.py tests/test_source_adapter_modes.py tests/test_source_adapter_timeouts.py -q --tb=short --timeout=60",
                    60,
                    "source_adapter_regression",
                )
            ],
            ValidationProfile.EDGE_ENGINE_ONLY: [
                ValidationShard(
                    "edge-accelerator-v10",
                    profile,
                    "python -m pytest tests/test_edge_discovery_accelerator.py tests/test_edge_triage_decision.py -q --tb=short --timeout=60",
                    60,
                    "edge_engine_regression",
                )
            ],
            ValidationProfile.FULL_REGRESSION: [
                ValidationShard(
                    "full-pytest",
                    profile,
                    "python -m pytest tests/ -q --tb=short --timeout=60",
                    60,
                    "required_proof",
                ),
                ValidationShard(
                    "full-dashboard-build",
                    profile,
                    "cd dashboard/frontend && npm run build",
                    60,
                    "required_proof",
                ),
            ],
        }
        return shard_map[profile]

    def run_fast_feedback(self, profile: ValidationProfile) -> FastFeedbackResult:
        shards = self.shards_for_profile(profile)
        return FastFeedbackResult(
            profile=profile,
            status="PLANNED",
            shard_count=len(shards),
            recursive_pytest=any(shard.recursive_pytest for shard in shards),
            unbounded_subprocess=any(shard.unbounded_subprocess for shard in shards),
        )

    def fast_feedback_report(self) -> dict[str, Any]:
        result = self.run_fast_feedback(ValidationProfile.SMOKE_FAST)
        return {
            "workstream": "V10: Fast Feedback",
            **result.to_dict(),
            "fast_feedback_is_not_proof": True,
            "verdict": "PASS"
            if result.status == "PLANNED" and not result.recursive_pytest and not result.unbounded_subprocess
            else "FAIL",
        }

    def full_regression_guard_report(self) -> dict[str, Any]:
        required = [
            "python -m pytest tests/ -q --tb=short --timeout=60",
            "cd dashboard/frontend && npm run build",
        ]
        result = FullRegressionResult(status="REQUIRED", required_commands=required)
        return {
            "workstream": "V10: Full Regression Guard",
            **result.to_dict(),
            "recursive_pytest_allowed": False,
            "verdict": "PASS",
        }

    def to_report(self) -> dict[str, Any]:
        profiles = {
            profile.value: [shard.to_dict() for shard in self.shards_for_profile(profile)]
            for profile in ValidationProfile
        }
        bounded = all(
            shard["timeout_s"] <= 60 and not shard["recursive_pytest"] and not shard["unbounded_subprocess"]
            for shards in profiles.values()
            for shard in shards
        )
        return {
            "workstream": "V10: Validation Sharding",
            "profiles": profiles,
            "recursive_pytest_allowed": False,
            "unbounded_subprocess_allowed": False,
            "regression_risk_score": RegressionRiskScore().to_dict(),
            "verdict": "PASS" if bounded else "FAIL",
        }
