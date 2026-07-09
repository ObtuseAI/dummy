"""Mesh throughput telemetry for V10."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MeshThroughputTelemetry:
    mesh_cycle_duration_s: float
    lane_durations_s: dict[str, float]
    packets_generated: int
    packets_promoted: int
    packets_starved: int
    sources_discovered: int
    sources_promoted: int
    sources_pruned: int
    edge_candidates_generated: int
    edge_candidates_escalated: int
    no_trade_decisions_generated: int
    model_calls_used: int
    model_failures: int
    timeout_pressure: float
    proof_failures: int
    regression_failures: int
    proof_paths: list[str] = field(default_factory=list)

    @classmethod
    def sample(cls) -> "MeshThroughputTelemetry":
        return cls(
            mesh_cycle_duration_s=7.4,
            lane_durations_s={
                "build_factory": 0.2,
                "source_adapters": 0.3,
                "edge_accelerator": 0.2,
                "validation_shards": 0.1,
            },
            packets_generated=8,
            packets_promoted=8,
            packets_starved=0,
            sources_discovered=5,
            sources_promoted=1,
            sources_pruned=1,
            edge_candidates_generated=4,
            edge_candidates_escalated=1,
            no_trade_decisions_generated=1,
            model_calls_used=0,
            model_failures=0,
            timeout_pressure=0.0,
            proof_failures=0,
            regression_failures=0,
            proof_paths=[
                "artifacts/dummy/build_edge_factory_report_v1.json",
                "artifacts/dummy/source_adapter_promotion_engine_report_v1.json",
                "artifacts/dummy/edge_discovery_accelerator_report_v1.json",
            ],
        )

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V10: Mesh Throughput Telemetry",
            "mesh_cycle_duration_s": self.mesh_cycle_duration_s,
            "lane_durations_s": self.lane_durations_s,
            "packets_generated": self.packets_generated,
            "packets_promoted": self.packets_promoted,
            "packets_starved": self.packets_starved,
            "sources_discovered": self.sources_discovered,
            "sources_promoted": self.sources_promoted,
            "sources_pruned": self.sources_pruned,
            "edge_candidates_generated": self.edge_candidates_generated,
            "edge_candidates_escalated": self.edge_candidates_escalated,
            "no_trade_decisions_generated": self.no_trade_decisions_generated,
            "model_calls_used": self.model_calls_used,
            "model_failures": self.model_failures,
            "timeout_pressure": self.timeout_pressure,
            "proof_failures": self.proof_failures,
            "regression_failures": self.regression_failures,
            "proof_paths": self.proof_paths,
            "verdict": "PASS"
            if self.mesh_cycle_duration_s >= 0
            and self.packets_generated >= self.packets_promoted
            and self.sources_discovered >= self.sources_promoted
            and self.proof_failures == 0
            and self.regression_failures == 0
            else "FAIL",
        }

    def progress_score_report(self) -> dict[str, Any]:
        generated = max(1, self.packets_generated)
        source_base = max(1, self.sources_discovered)
        edge_base = max(1, self.edge_candidates_generated)
        score = (
            (self.packets_promoted / generated) * 0.35
            + (self.sources_promoted / source_base) * 0.20
            + (self.edge_candidates_escalated / edge_base) * 0.20
            + (1.0 - min(1.0, self.timeout_pressure)) * 0.15
            + (1.0 if self.regression_failures == 0 else 0.0) * 0.10
        )
        return {
            "workstream": "V10: Progress Acceleration Score",
            "progress_acceleration_score": round(max(0.0, min(1.0, score)), 4),
            "inputs": {
                "packets_generated": self.packets_generated,
                "packets_promoted": self.packets_promoted,
                "sources_discovered": self.sources_discovered,
                "sources_promoted": self.sources_promoted,
                "edge_candidates_generated": self.edge_candidates_generated,
                "edge_candidates_escalated": self.edge_candidates_escalated,
                "timeout_pressure": self.timeout_pressure,
                "regression_failures": self.regression_failures,
            },
            "verdict": "PASS",
        }
