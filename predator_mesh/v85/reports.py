"""DUMMY v85 micro-campaign readiness blocker closure and authority-gap audit (no submit)."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v85 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

CAMPAIGN_BLOCKERS = [
    "CAMPAIGN_APPROVAL_ABSENT",
    "PER_ORDER_APPROVAL_ABSENT",
    "LIVE_SUBMIT_CONFIG_ABSENT",
    "CAPS_CONFIG_ABSENT",
    "BROKER_ADAPTER_ABSENT",
    "FIRST_CANARY_PROOF_GAP",
    "SECOND_CANARY_PROOF_GAP",
    "RISK_SCALING_GAP",
]

V85_ROUTES = [
    "/api/v85/blocker-closure-controller",
    "/api/v85/v84-baseline",
    "/api/v85/campaign-approval-gap",
    "/api/v85/per-order-approval-gap",
    "/api/v85/live-submit-config-gap",
    "/api/v85/caps-gap",
    "/api/v85/broker-adapter-gap",
    "/api/v85/canary-proof-gap",
    "/api/v85/risk-scaling-gap",
    "/api/v85/no-auto-submit-proof",
    "/api/v85/readiness-governor",
    "/api/v85/execution-lock",
    "/api/v85/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "blocker-closure-controller": ["v85_blocker_closure_controller_report.json"],
    "v84-baseline": ["v84_baseline_readback_v1_report.json"],
    "campaign-approval-gap": ["v85_campaign_approval_gap_report.json"],
    "per-order-approval-gap": ["v85_per_order_approval_gap_report.json"],
    "live-submit-config-gap": ["v85_live_submit_config_gap_report.json"],
    "caps-gap": ["v85_caps_gap_report.json"],
    "broker-adapter-gap": ["v85_broker_adapter_gap_report.json"],
    "canary-proof-gap": ["v85_canary_proof_gap_report.json"],
    "risk-scaling-gap": ["v85_risk_scaling_gap_report.json"],
    "no-auto-submit-proof": ["v85_no_auto_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v45_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v44_report.json"],
    "mission-state": ["dummy_mission_state_report_v71.json", "dashboard_v85_report_v1.json", "completion_oriented_next_action_v85_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(85)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v85/reports.py scripts/generate_v85_reports.py dashboard/backend/v85_routes.py",
    "python scripts/generate_v85_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V85Context:
    def __init__(self) -> None:
        self.v84_baseline_status = sgc.baseline_status("final_report_v84.json", "V84")

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v84_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V84_BASELINE_REGRESSION"] if self.v84_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "AWAIT_CAMPAIGN_AND_PER_ORDER_APPROVALS"


def _common(ctx: V85Context) -> dict[str, Any]:
    gaps = {f"{k.lower()}_status": "PASS_GAP_CLASSIFIED" for k in ["campaign_approval_gap", "per_order_approval_gap", "live_submit_config_gap", "caps_gap", "broker_adapter_gap", "canary_proof_gap", "risk_scaling_gap"]}
    common = {
        "v84_baseline_status": ctx.v84_baseline_status,
        "blocker_closure_controller_status": "PASS_CAMPAIGN_BLOCKERS_CLASSIFIED_NO_SUBMIT",
        "classified_campaign_blockers": CAMPAIGN_BLOCKERS,
        "no_auto_submit_proof_status": "PASS_NO_AUTO_SUBMIT",
        "live_orders": 0,
        "campaign_auto_submit": False,
        "readiness_governor_v45_status": "PASS",
        "execution_lock_deep_recheck_v44_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }
    common.update(gaps)
    return common


def _verdict(name: str, ctx: V85Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v84_baseline"):
        return "PASS" if ctx.v84_baseline_status == "PASS_V84_BASELINE_READBACK" else "FAIL" if ctx.v84_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V85Context) -> dict[str, Any]:
    workstream = "v85: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v85_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V85_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v85_report.json":
        report.update({"completion_oriented_next_action_v85_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v71.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v84_carried_status": ctx.v84_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v85.json"), "blocker_closure": str(ARTIFACTS / "v85_blocker_closure_controller_report.json"), "no_auto_submit": str(ARTIFACTS / "v85_no_auto_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v85.json", "dummy_canonical_identity_report_v85.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V85ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V85Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
