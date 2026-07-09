"""Redacted operator repair packet for Kalshi READ_ONLY V13 closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge
from predator_mesh.v13.orderbook_snapshot_v2 import RealOrderbookSnapshotClosure


@dataclass(frozen=True)
class KalshiCredentialRepairStep:
    name: str
    status: str
    placeholder_example: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "placeholder_example": self.placeholder_example,
        }


@dataclass(frozen=True)
class KalshiOrderbookRepairStep:
    name: str
    status: str
    placeholder_example: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "placeholder_example": self.placeholder_example,
        }


class KalshiReadOnlyOperatorRepairPacket:
    def __init__(
        self,
        *,
        credential_bridge: KalshiReadOnlyCredentialBridge | None = None,
        snapshot_closure: RealOrderbookSnapshotClosure | None = None,
    ) -> None:
        self.credential_bridge = credential_bridge or KalshiReadOnlyCredentialBridge()
        self.snapshot_closure = snapshot_closure

    def to_report(self) -> dict[str, Any]:
        readiness = self.credential_bridge.resolve()
        closure = self.snapshot_closure
        discovery_passed = bool(closure and closure.discovery.real_read_only_used)
        snapshot_passed = bool(closure and closure.outcome == "REAL_READ_ONLY")
        auth_probe_passed = readiness.ready and (
            closure is None
            or closure.discovery.degradation_reason
            not in {"CREDENTIALS_INVALID", "CREDENTIALS_MISSING", "REAL_READ_ONLY_DEGRADED", "DISCOVERY_TIMEOUT"}
        )
        steps = [
            KalshiCredentialRepairStep(
                "Provide key id",
                "PASS" if readiness.key_id_present else "MISSING",
                "KALSHI_API_KEY_ID=<your-key-id>",
            ).to_dict(),
            KalshiCredentialRepairStep(
                "Provide private key source",
                "PASS" if readiness.private_key_source_present else "MISSING",
                "KALSHI_API_PRIVATE_KEY_PEM_PATH=C:/path/to/kalshi-key.pem",
            ).to_dict(),
            KalshiOrderbookRepairStep(
                "Confirm eligible active market",
                "PASS" if discovery_passed else "NOT_PROVEN",
                "Use bounded READ_ONLY market discovery; do not submit or cancel orders.",
            ).to_dict(),
            KalshiOrderbookRepairStep(
                "Confirm nonempty orderbook snapshot",
                "PASS" if snapshot_passed else "NOT_PROVEN",
                "Use GET /markets/{ticker}/orderbook with <=10s request timeout.",
            ).to_dict(),
        ]
        verdict = "PASS" if readiness.ready and snapshot_passed else "OPERATOR_ACTION_REQUIRED"
        return {
            "workstream": "V13: Kalshi READ_ONLY Operator Repair Packet",
            "credential_status": readiness.to_dict(),
                "auth_probe_passed": auth_probe_passed,
            "market_discovery_passed": discovery_passed,
            "orderbook_snapshot_passed": snapshot_passed,
            "repair_steps": steps,
            "secret_values_included": False,
            "private_key_material_included": False,
            "verdict": verdict,
        }
