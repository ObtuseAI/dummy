"""V14 micro-order dry-run packet, rehearsal only."""

from __future__ import annotations

from typing import Any

from predator_mesh.v14.launch_readiness import LiquidityLaunchReadinessMatrix


class MicroOrderDryRunPacketV2:
    def __init__(self, *, forensics_report: dict[str, Any] | None = None) -> None:
        self.forensics_report = forensics_report

    def to_report(self) -> dict[str, Any]:
        readiness = LiquidityLaunchReadinessMatrix(forensics_report=self.forensics_report)
        blockers = readiness.blockers()
        return {
            "workstream": "V14: Micro Order Dry Run Packet V2",
            "would_submit": False,
            "live_submit_enabled": False,
            "allowed_submit_path": "LiveBrokerFirewall.submit",
            "direct_order_endpoints_allowed": False,
            "direct_cancel_endpoints_allowed": False,
            "limit_only": True,
            "tiny_size_only": True,
            "forbidden_order_types": ["MARKET"],
            "blockers": blockers,
            "verdict": "PARTIAL" if blockers else "PASS",
        }


class MicroOrderDryRunBlockerReport:
    def __init__(self, *, forensics_report: dict[str, Any] | None = None) -> None:
        self.forensics_report = forensics_report

    def to_report(self) -> dict[str, Any]:
        packet = MicroOrderDryRunPacketV2(forensics_report=self.forensics_report).to_report()
        return {
            "workstream": "V14: Micro Order Dry Run Blocker Report",
            "would_submit": False,
            "blockers": packet["blockers"],
            "operator_action": "Repair credentials and prove real READ_ONLY terrain before any operator-armed rehearsal.",
            "verdict": "PARTIAL" if packet["blockers"] else "PASS",
        }
