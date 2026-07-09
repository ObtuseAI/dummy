"""V14 liquidity launch readiness reports."""

from __future__ import annotations

from typing import Any

from predator_mesh.v14.credential_forensics import KalshiCredentialForensics


class LiquidityLaunchReadinessMatrix:
    def __init__(self, *, forensics_report: dict[str, Any] | None = None) -> None:
        self.forensics_report = forensics_report

    def _forensics(self) -> dict[str, Any]:
        return self.forensics_report or KalshiCredentialForensics().to_report()

    def _credential_blocker(self) -> str | None:
        reason = self._forensics().get("failure_reason", "CREDENTIALS_MISSING")
        if reason == "NONE":
            return None
        if reason == "CREDENTIALS_MISSING":
            return "CREDENTIALS_MISSING"
        return "CREDENTIALS_INVALID"

    def blockers(self) -> list[str]:
        blockers = ["LIVE_SUBMIT_DISABLED", "REAL_TERRAIN_NOT_PROVEN"]
        credential = self._credential_blocker()
        if credential:
            blockers.insert(0, credential)
        return blockers

    def gate_output(self) -> str:
        credential = self._credential_blocker()
        if credential:
            return "READY_FOR_OPERATOR_ARMED_MICRO_ORDER_ONLY_AFTER_CREDENTIAL_REPAIR"
        return "READY_FOR_OPERATOR_ARMED_MICRO_ORDER_REHEARSAL_ONLY"

    def to_report(self) -> dict[str, Any]:
        blockers = self.blockers()
        categories = {
            "credential readiness": 0.0 if self._credential_blocker() else 1.0,
            "real terrain proof": 0.0,
            "liquidity gates": 0.65,
            "firewall and caps": 0.5,
            "runtime evidence": 1.0,
        }
        readiness_score = round(sum(categories.values()) / len(categories), 4)
        return {
            "workstream": "V14: Liquidity Launch Readiness Matrix",
            "categories": categories,
            "readiness_score": readiness_score,
            "blockers": blockers,
            "gate_output": self.gate_output(),
            "operator_armed_micro_order_ready": False,
            "verdict": "PARTIAL" if blockers else "PASS",
        }

    def blocker_report(self) -> dict[str, Any]:
        blockers = self.blockers()
        return {
            "workstream": "V14: Liquidity Launch Blocker Report",
            "blockers": blockers,
            "live_submit_enabled": False,
            "verdict": "PARTIAL" if blockers else "PASS",
        }

    def operator_readiness_report(self) -> dict[str, Any]:
        return {
            "workstream": "V14: Operator Armed Micro Order Readiness",
            "ready_for_operator_armed_micro_order": False,
            "gate_output": self.gate_output(),
            "limit_only": True,
            "tiny_size_only": True,
            "requires_operator_credential_repair": self._credential_blocker() is not None,
            "verdict": "PARTIAL",
        }
