"""Build acceleration queue for bounded V10 packets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from predator_mesh.v10.build_factory import BuildPacket


@dataclass(frozen=True)
class QueuePriorityScore:
    expected_edge_contribution: float
    source_category_value: float
    proof_difficulty: float
    implementation_cost: float
    test_cost: float
    dashboard_value: float
    calibration_value: float
    risk_intelligence_value: float
    duplicate_source_penalty: float = 0.0
    stale_source_penalty: float = 0.0
    blocked_dependency_penalty: float = 0.0
    total: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_edge_contribution": self.expected_edge_contribution,
            "source_category_value": self.source_category_value,
            "proof_difficulty": self.proof_difficulty,
            "implementation_cost": self.implementation_cost,
            "test_cost": self.test_cost,
            "dashboard_value": self.dashboard_value,
            "calibration_value": self.calibration_value,
            "risk_intelligence_value": self.risk_intelligence_value,
            "duplicate_source_penalty": self.duplicate_source_penalty,
            "stale_source_penalty": self.stale_source_penalty,
            "blocked_dependency_penalty": self.blocked_dependency_penalty,
            "total": self.total,
        }


@dataclass(frozen=True)
class QueueItem:
    item_id: str
    packet: BuildPacket
    score: QueuePriorityScore
    status: str = "QUEUED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "packet_id": self.packet.packet_id,
            "packet_type": self.packet.packet_type.value,
            "priority": self.packet.priority.value,
            "status": self.status,
            "score": self.score.to_dict(),
        }


@dataclass(frozen=True)
class QueueDispatchDecision:
    item_id: str
    packet_id: str
    decision: str
    reason: str
    score_total: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "packet_id": self.packet_id,
            "decision": self.decision,
            "reason": self.reason,
            "score_total": self.score_total,
        }


@dataclass(frozen=True)
class QueueBackpressureState:
    queued: int
    max_queue_size: int = 12

    @property
    def status(self) -> str:
        return "NORMAL" if self.queued <= self.max_queue_size else "BACKPRESSURE"

    def to_dict(self) -> dict[str, Any]:
        return {"queued": self.queued, "max_queue_size": self.max_queue_size, "status": self.status}


@dataclass(frozen=True)
class QueueStalenessState:
    stale_items: int
    max_stale_items: int = 0

    @property
    def status(self) -> str:
        return "FRESH" if self.stale_items <= self.max_stale_items else "STALE_PRESSURE"

    def to_dict(self) -> dict[str, Any]:
        return {"stale_items": self.stale_items, "max_stale_items": self.max_stale_items, "status": self.status}


class BuildAccelerationQueue:
    def __init__(self) -> None:
        self.items: list[QueueItem] = []

    def score_packet(
        self,
        packet: BuildPacket,
        *,
        duplicate: bool = False,
        stale: bool = False,
        blocked_dependency: bool = False,
    ) -> QueuePriorityScore:
        category_value = {
            "crypto_btc": 0.90,
            "edge_hypothesis": 0.86,
            "validation": 0.70,
            "macro_weather": 0.68,
            "mesh_throughput": 0.62,
            "dashboard": 0.58,
            "risk_intelligence": 0.56,
            "proof": 0.54,
        }.get(packet.source_category, 0.50)
        dashboard_value = 0.20 if "dashboard" in packet.source_category else 0.08
        calibration_value = 0.18 if "calibration" in packet.source_category else 0.10
        risk_value = 0.18 if "risk" in packet.source_category or "edge" in packet.source_category else 0.09
        test_cost = min(0.35, len(packet.proof_gate.required_tests) * 0.08)
        duplicate_penalty = 0.18 if duplicate else 0.0
        stale_penalty = 0.16 if stale else 0.0
        blocked_penalty = 0.24 if blocked_dependency else 0.0
        total = (
            packet.expected_edge_contribution * 0.34
            + category_value * 0.18
            + dashboard_value
            + calibration_value
            + risk_value
            - packet.proof_difficulty * 0.10
            - packet.implementation_cost * 0.10
            - test_cost
            - duplicate_penalty
            - stale_penalty
            - blocked_penalty
        )
        return QueuePriorityScore(
            expected_edge_contribution=packet.expected_edge_contribution,
            source_category_value=category_value,
            proof_difficulty=packet.proof_difficulty,
            implementation_cost=packet.implementation_cost,
            test_cost=test_cost,
            dashboard_value=dashboard_value,
            calibration_value=calibration_value,
            risk_intelligence_value=risk_value,
            duplicate_source_penalty=duplicate_penalty,
            stale_source_penalty=stale_penalty,
            blocked_dependency_penalty=blocked_penalty,
            total=round(max(0.01, total), 4),
        )

    def enqueue(self, packet: BuildPacket) -> QueueItem:
        item = QueueItem(
            item_id=f"queue-{len(self.items) + 1:03d}",
            packet=packet,
            score=self.score_packet(packet),
        )
        self.items.append(item)
        return item

    def dispatch(self, item: QueueItem) -> QueueDispatchDecision:
        if item.score.blocked_dependency_penalty > 0:
            decision = "REQUIRE_MORE_EVIDENCE"
            reason = "Blocked dependency requires more proof before dispatch."
        elif item.score.total >= 0.42:
            decision = "DISPATCH_NOW"
            reason = "High proof-adjusted build value."
        elif item.score.total >= 0.25:
            decision = "DEFER"
            reason = "Useful packet, but not top of queue."
        else:
            decision = "REQUIRE_MORE_EVIDENCE"
            reason = "Score is below dispatch threshold."
        return QueueDispatchDecision(
            item_id=item.item_id,
            packet_id=item.packet.packet_id,
            decision=decision,
            reason=reason,
            score_total=item.score.total,
        )

    def to_report(self) -> dict[str, Any]:
        decisions = [self.dispatch(item) for item in self.items]
        return {
            "workstream": "V10: Build Acceleration Queue",
            "item_count": len(self.items),
            "items": [item.to_dict() for item in self.items],
            "dispatch_decisions": [decision.to_dict() for decision in decisions],
            "backpressure": QueueBackpressureState(len(self.items)).to_dict(),
            "staleness": QueueStalenessState(0).to_dict(),
            "allowed_decisions": [
                "DISPATCH_NOW",
                "DEFER",
                "REQUIRE_MORE_EVIDENCE",
                "MERGE_WITH_EXISTING_PACKET",
                "STARVE_PACKET",
                "QUARANTINE_PACKET",
            ],
            "verdict": "PASS" if self.items else "FAIL",
        }

    def priority_report(self) -> dict[str, Any]:
        return {
            "workstream": "V10: Build Queue Priority",
            "scores": [
                {"packet_id": item.packet.packet_id, **item.score.to_dict()}
                for item in self.items
            ],
            "verdict": "PASS" if self.items else "FAIL",
        }
