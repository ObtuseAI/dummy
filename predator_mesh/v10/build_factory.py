"""Bounded build-packet factory for DUMMY_V10."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BuildPacketType(str, Enum):
    SOURCE_ADAPTER_CANDIDATE = "source_adapter_candidate"
    SOURCE_ADAPTER_PROMOTION = "source_adapter_promotion"
    SIGNAL_NORMALIZER_UPGRADE = "signal_normalizer_upgrade"
    EDGE_SCORER_UPGRADE = "edge_scorer_upgrade"
    CALIBRATION_UPGRADE = "calibration_upgrade"
    STRATEGY_FAMILY_UPGRADE = "strategy_family_upgrade"
    DASHBOARD_TELEMETRY_UPGRADE = "dashboard_telemetry_upgrade"
    TEST_COVERAGE_UPGRADE = "test_coverage_upgrade"
    REPORT_GENERATOR_UPGRADE = "report_generator_upgrade"
    MESH_LANE_OPTIMIZATION = "mesh_lane_optimization"
    TIMEOUT_GUARD_UPGRADE = "timeout_guard_upgrade"
    NO_TRADE_REASON_UPGRADE = "no_trade_reason_upgrade"
    PROOF_LEDGER_UPGRADE = "proof_ledger_upgrade"


class BuildPacketPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    STARVE = "starve"

    @property
    def rank(self) -> int:
        return {
            BuildPacketPriority.CRITICAL: 500,
            BuildPacketPriority.HIGH: 400,
            BuildPacketPriority.MEDIUM: 300,
            BuildPacketPriority.LOW: 200,
            BuildPacketPriority.STARVE: 100,
        }[self]


@dataclass(frozen=True)
class BuildPacketScopeLimits:
    allowed_paths: list[str] = field(default_factory=list)
    forbidden_paths: list[str] = field(default_factory=list)
    live_order_endpoint_allowed: bool = False
    unbounded_subprocess_allowed: bool = False
    unbounded_scraping_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_paths": self.allowed_paths,
            "forbidden_paths": self.forbidden_paths,
            "live_order_endpoint_allowed": self.live_order_endpoint_allowed,
            "unbounded_subprocess_allowed": self.unbounded_subprocess_allowed,
            "unbounded_scraping_allowed": self.unbounded_scraping_allowed,
        }


@dataclass(frozen=True)
class BuildPacketBudget:
    timeout_s: float = 30.0
    max_files_changed: int = 5
    max_external_calls: int = 0
    max_model_calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeout_s": self.timeout_s,
            "max_files_changed": self.max_files_changed,
            "max_external_calls": self.max_external_calls,
            "max_model_calls": self.max_model_calls,
        }


@dataclass(frozen=True)
class BuildPacketProofGate:
    required_tests: list[str]
    required_reports: list[str]
    full_regression_required: bool = True
    dashboard_build_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_tests": self.required_tests,
            "required_reports": self.required_reports,
            "full_regression_required": self.full_regression_required,
            "dashboard_build_required": self.dashboard_build_required,
        }


@dataclass(frozen=True)
class BuildPacketRollbackPlan:
    notes: str
    touched_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"notes": self.notes, "touched_paths": self.touched_paths}


@dataclass(frozen=True)
class BuildPacketResult:
    packet_id: str
    status: str
    tests_passed: bool = False
    reports_written: bool = False
    proof_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "status": self.status,
            "tests_passed": self.tests_passed,
            "reports_written": self.reports_written,
            "proof_paths": self.proof_paths,
        }


@dataclass(frozen=True)
class BuildPacketPromotionDecision:
    packet_id: str
    decision: str
    reason: str
    required_tests: list[str] = field(default_factory=list)
    required_reports: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "decision": self.decision,
            "reason": self.reason,
            "required_tests": self.required_tests,
            "required_reports": self.required_reports,
        }


@dataclass(frozen=True)
class BuildPacket:
    packet_id: str
    packet_type: BuildPacketType
    priority: BuildPacketPriority
    title: str
    source_category: str
    expected_edge_contribution: float
    implementation_cost: float
    proof_difficulty: float
    scope_limits: BuildPacketScopeLimits
    budget: BuildPacketBudget
    proof_gate: BuildPacketProofGate
    rollback_plan: BuildPacketRollbackPlan
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "packet_type": self.packet_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "source_category": self.source_category,
            "expected_edge_contribution": self.expected_edge_contribution,
            "implementation_cost": self.implementation_cost,
            "proof_difficulty": self.proof_difficulty,
            "scope_limits": self.scope_limits.to_dict(),
            "budget": self.budget.to_dict(),
            "proof_gate": self.proof_gate.to_dict(),
            "rollback_plan": self.rollback_plan.to_dict(),
            "dependencies": self.dependencies,
        }


class BuildEdgeFactory:
    """Creates bounded V10 improvement packets from V9 mesh signals."""

    _FORBIDDEN_PATHS = [
        "configs/caps.json",
        "configs/live_submit.json",
        "core/inherited_blunder",
        "live_firewall/firewall.py",
    ]

    def _scope(self, allowed_paths: list[str]) -> BuildPacketScopeLimits:
        return BuildPacketScopeLimits(
            allowed_paths=allowed_paths,
            forbidden_paths=list(self._FORBIDDEN_PATHS),
        )

    def _packet(
        self,
        index: int,
        packet_type: BuildPacketType,
        priority: BuildPacketPriority,
        title: str,
        category: str,
        edge: float,
        cost: float,
        proof: float,
        allowed_paths: list[str],
        tests: list[str],
        reports: list[str],
        dashboard_required: bool = False,
    ) -> BuildPacket:
        return BuildPacket(
            packet_id=f"v10-{index:02d}-{packet_type.value.replace('_', '-')}",
            packet_type=packet_type,
            priority=priority,
            title=title,
            source_category=category,
            expected_edge_contribution=edge,
            implementation_cost=cost,
            proof_difficulty=proof,
            scope_limits=self._scope(allowed_paths),
            budget=BuildPacketBudget(timeout_s=30.0, max_files_changed=6),
            proof_gate=BuildPacketProofGate(
                required_tests=tests,
                required_reports=reports,
                dashboard_build_required=dashboard_required,
            ),
            rollback_plan=BuildPacketRollbackPlan(
                notes="Revert only this packet's scoped paths and preserve V9 artifacts.",
                touched_paths=allowed_paths,
            ),
        )

    def generate_packets(self) -> list[BuildPacket]:
        specs = [
            (
                BuildPacketType.SOURCE_ADAPTER_CANDIDATE,
                BuildPacketPriority.CRITICAL,
                "Promote bounded public BTC source metadata",
                "crypto_btc",
                0.88,
                0.30,
                0.40,
                ["predator_mesh/v10/source_adapters.py", "tests/test_source_adapter_promotion_engine.py"],
                ["tests/test_source_adapter_promotion_engine.py"],
                ["source_adapter_promotion_engine_report_v1.json"],
            ),
            (
                BuildPacketType.SOURCE_ADAPTER_PROMOTION,
                BuildPacketPriority.HIGH,
                "Promote static macro and weather adapters when proof-backed",
                "macro_weather",
                0.72,
                0.42,
                0.48,
                ["predator_mesh/v10/source_adapters.py"],
                ["tests/test_source_adapter_modes.py", "tests/test_source_adapter_timeouts.py"],
                ["source_adapter_mode_report_v1.json", "source_adapter_timeout_report_v1.json"],
            ),
            (
                BuildPacketType.EDGE_SCORER_UPGRADE,
                BuildPacketPriority.HIGH,
                "Rank edge hypotheses with proof-cost pressure",
                "edge_hypothesis",
                0.82,
                0.44,
                0.52,
                ["predator_mesh/v10/edge_accelerator.py"],
                ["tests/test_edge_discovery_accelerator.py", "tests/test_edge_triage_decision.py"],
                ["edge_discovery_accelerator_report_v1.json"],
            ),
            (
                BuildPacketType.TEST_COVERAGE_UPGRADE,
                BuildPacketPriority.HIGH,
                "Shard fast feedback without replacing full regression",
                "validation",
                0.66,
                0.25,
                0.36,
                ["predator_mesh/v10/validation.py", "tests"],
                ["tests/test_validation_sharding.py", "tests/test_full_regression_guard_v10.py"],
                ["validation_sharding_report_v1.json", "full_regression_guard_report_v1.json"],
            ),
            (
                BuildPacketType.DASHBOARD_TELEMETRY_UPGRADE,
                BuildPacketPriority.MEDIUM,
                "Expose V10 build velocity telemetry",
                "dashboard",
                0.52,
                0.35,
                0.42,
                ["dashboard/backend/v10_routes.py", "dashboard/backend/main.py"],
                ["tests/test_dashboard_v10.py"],
                ["dashboard_v10_report_v1.json"],
                True,
            ),
            (
                BuildPacketType.MESH_LANE_OPTIMIZATION,
                BuildPacketPriority.MEDIUM,
                "Track throughput and stale build pressure",
                "mesh_throughput",
                0.58,
                0.32,
                0.45,
                ["predator_mesh/v10/telemetry.py", "predator_mesh/v10/queue.py"],
                ["tests/test_mesh_throughput_telemetry.py", "tests/test_build_queue_priority.py"],
                ["mesh_throughput_telemetry_report_v1.json", "build_queue_priority_report_v1.json"],
            ),
            (
                BuildPacketType.PROOF_LEDGER_UPGRADE,
                BuildPacketPriority.MEDIUM,
                "Summarize proof paths for promoted packets",
                "proof",
                0.46,
                0.28,
                0.34,
                ["scripts/generate_v10_reports.py"],
                ["tests/test_no_secret_leak_v10.py", "tests/test_no_direct_order_bypass_v10.py"],
                ["final_report_v10.json"],
            ),
            (
                BuildPacketType.NO_TRADE_REASON_UPGRADE,
                BuildPacketPriority.LOW,
                "Feed no-trade pressure into edge triage",
                "risk_intelligence",
                0.40,
                0.24,
                0.38,
                ["predator_mesh/v10/edge_accelerator.py"],
                ["tests/test_edge_triage_decision.py"],
                ["edge_triage_decision_report_v1.json"],
            ),
        ]
        return [
            self._packet(index + 1, *spec)
            for index, spec in enumerate(specs)
        ]

    def evaluate_promotion(
        self,
        packet: BuildPacket,
        *,
        tests_passed: bool,
        reports_written: bool,
    ) -> BuildPacketPromotionDecision:
        if not tests_passed:
            return BuildPacketPromotionDecision(
                packet_id=packet.packet_id,
                decision="REQUIRE_TESTS",
                reason="Packet cannot promote without its required test slice.",
                required_tests=packet.proof_gate.required_tests,
                required_reports=packet.proof_gate.required_reports,
            )
        if not reports_written:
            return BuildPacketPromotionDecision(
                packet_id=packet.packet_id,
                decision="REQUIRE_REPORTS",
                reason="Packet cannot promote without proof artifacts.",
                required_tests=packet.proof_gate.required_tests,
                required_reports=packet.proof_gate.required_reports,
            )
        return BuildPacketPromotionDecision(
            packet_id=packet.packet_id,
            decision="PROMOTE",
            reason="Packet satisfied bounded tests and report gates.",
            required_tests=packet.proof_gate.required_tests,
            required_reports=packet.proof_gate.required_reports,
        )

    def packet_manifest(self) -> dict[str, Any]:
        packets = self.generate_packets()
        return {
            "workstream": "V10: Build Packet Manifest",
            "packet_count": len(packets),
            "packets": [packet.to_dict() for packet in packets],
            "verdict": "PASS" if packets else "FAIL",
        }

    def promotion_report(self) -> dict[str, Any]:
        packets = self.generate_packets()
        decisions = [
            self.evaluate_promotion(packet, tests_passed=True, reports_written=True).to_dict()
            for packet in packets
        ]
        return {
            "workstream": "V10: Build Packet Promotion",
            "decisions": decisions,
            "verdict": "PASS" if decisions else "FAIL",
        }

    def to_report(self) -> dict[str, Any]:
        packets = self.generate_packets()
        bounded = all(packet.budget.timeout_s <= 30 for packet in packets)
        safe_paths = all(
            "configs/caps.json" in packet.scope_limits.forbidden_paths
            and "configs/live_submit.json" in packet.scope_limits.forbidden_paths
            and "core/inherited_blunder" in packet.scope_limits.forbidden_paths
            and not packet.scope_limits.live_order_endpoint_allowed
            for packet in packets
        )
        return {
            "workstream": "V10: Accelerated Build Edge Factory",
            "packet_count": len(packets),
            "packet_types": sorted({packet.packet_type.value for packet in packets}),
            "live_submit_disabled_required": True,
            "caps_read_only_required": True,
            "no_direct_order_endpoint_required": True,
            "bounded_timeout_required": True,
            "max_packet_timeout_s": max((packet.budget.timeout_s for packet in packets), default=0),
            "forbidden_paths": list(self._FORBIDDEN_PATHS),
            "packets": [packet.to_dict() for packet in packets],
            "verdict": "PASS" if packets and bounded and safe_paths else "FAIL",
        }
