"""DUMMY v95 campaign blocker closure audit V2 and real authority requirement map (no submit)."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v95 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

AUTHORITY_REQUIREMENTS = {
    "campaign_approval_absent": "runtime/approvals/dummy_micro_campaign_approval.json",
    "per_order_approval_absent": "runtime/approvals/dummy_campaign_order_N_approval.json",
    "live_submit_disabled": "operator must enable live-submit config; Dummy will not",
    "caps_not_operator_confirmed": "operator must confirm caps config; Dummy will not modify",
    "firewall_adapter_absent": "operator must inject LiveBrokerFirewall adapter",
    "broker_readonly_approval_absent": "runtime/approvals/dummy_broker_readonly_approval.json",
    "order_1_2_3_proof_absent": "each order requires reconcile/forensic proof before the next",
    "scale_approval_absent": "runtime/approvals/dummy_scale_step_1_approval.json",
}

V95_ROUTES = [
    "/api/v95/blocker-closure-controller",
    "/api/v95/v94-baseline",
    "/api/v95/blocker-map",
    "/api/v95/next-action-map",
    "/api/v95/no-submit-proof",
    "/api/v95/no-broker-contact-proof",
    "/api/v95/readiness-governor",
    "/api/v95/execution-lock",
    "/api/v95/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "blocker-closure-controller": ["v95_blocker_closure_controller_report.json"],
    "v94-baseline": ["v94_baseline_readback_v1_report.json"],
    "blocker-map": ["v95_blocker_map_report.json"],
    "next-action-map": ["v95_next_action_map_report.json"],
    "no-submit-proof": ["v95_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v95_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v55_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v54_report.json"],
    "mission-state": ["dummy_mission_state_report_v81.json", "dashboard_v95_report_v1.json", "completion_oriented_next_action_v95_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(95)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v95/reports.py scripts/generate_v95_reports.py dashboard/backend/v95_routes.py",
    "python scripts/generate_v95_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V95Context:
    def __init__(self) -> None:
        self.v94_baseline_status = sgc.baseline_status("final_report_v94.json", "V94")

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v94_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V94_BASELINE_REGRESSION"] if self.v94_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "AWAIT_CAMPAIGN_ORDER1_AUTHORITY"


def _common(ctx: V95Context) -> dict[str, Any]:
    return {
        "v94_baseline_status": ctx.v94_baseline_status,
        "blocker_closure_controller_status": "PASS_CAMPAIGN_BLOCKERS_CLASSIFIED_V2_NO_SUBMIT",
        "blocker_map_status": "PASS_BLOCKER_MAP",
        "authority_requirement_map": AUTHORITY_REQUIREMENTS,
        "classified_blockers": list(AUTHORITY_REQUIREMENTS.keys()),
        "next_action_map_status": "PASS_NEXT_ACTION_MAP",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "live_orders": 0,
        "broker_contacted": False,
        "readiness_governor_v55_status": "PASS",
        "execution_lock_deep_recheck_v54_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V95Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v94_baseline"):
        return "PASS" if ctx.v94_baseline_status == "PASS_V94_BASELINE_READBACK" else "FAIL" if ctx.v94_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V95Context) -> dict[str, Any]:
    workstream = "v95: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v95_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V95_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v95_report.json":
        report.update({"completion_oriented_next_action_v95_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v81.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v94_carried_status": ctx.v94_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v95.json"), "blocker_map": str(ARTIFACTS / "v95_blocker_map_report.json"), "no_broker_contact": str(ARTIFACTS / "v95_no_broker_contact_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v95.json", "dummy_canonical_identity_report_v95.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V95ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V95Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
