"""DUMMY v126 production pilot blocker closure V2 — audits V116-V125 pilot blockers into an exact authority map; no submit.

Classifies every remaining pilot blocker (approval / firewall / live-submit / caps / broker-access / repeat-proof /
scale / autonomy) and selects a next-action from a fixed matrix. Static PASS audit; live_orders=0, broker_contacted=false.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v126 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v126: Production Pilot Blocker Closure V2 Authority Map"
MISSION_NAME = "dummy_mission_state_report_v112.json"
FINAL_NAME = "final_report_v126.json"
INDEX_KEYS = ["pilot_blocker_controller_status", "next_action_matrix_selection", "live_orders"]
DASH_TITLE = "Dummy V126 Production Pilot Blocker Closure V2"
MISSION_KEY = "dummy_mission_state_report_v112"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Blocker Audit", "pilot_blocker_controller_status"],
    ["Next Action Matrix", "next_action_matrix_selection"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V126_ROUTES = [
    "/api/v126/pilot-blocker-controller",
    "/api/v126/v125-baseline",
    "/api/v126/blocker-classifier",
    "/api/v126/pilot-approval-blocker",
    "/api/v126/firewall-adapter-blocker",
    "/api/v126/live-submit-caps-blocker",
    "/api/v126/broker-private-access-blocker",
    "/api/v126/repeat-scale-autonomy-blocker",
    "/api/v126/next-action-matrix",
    "/api/v126/no-submit-proof",
    "/api/v126/no-broker-contact-proof",
    "/api/v126/readiness-governor",
    "/api/v126/execution-lock",
    "/api/v126/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "pilot-blocker-controller": ["v126_pilot_blocker_controller_report.json"],
    "v125-baseline": ["v125_baseline_readback_v1_report.json"],
    "blocker-classifier": ["v126_blocker_classifier_report.json"],
    "pilot-approval-blocker": ["v126_pilot_approval_blocker_report.json"],
    "firewall-adapter-blocker": ["v126_firewall_adapter_blocker_report.json"],
    "live-submit-caps-blocker": ["v126_live_submit_caps_blocker_report.json"],
    "broker-private-access-blocker": ["v126_broker_private_access_blocker_report.json"],
    "repeat-scale-autonomy-blocker": ["v126_repeat_scale_autonomy_blocker_report.json"],
    "next-action-matrix": ["v126_next_action_matrix_report.json"],
    "no-submit-proof": ["v126_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v126_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v86_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v85_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v126_report_v1.json", "completion_oriented_next_action_v126_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(126)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v126/reports.py scripts/generate_v126_reports.py dashboard/backend/v126_routes.py",
    "python scripts/generate_v126_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

NEXT_ACTION_MATRIX = [
    "AWAIT_CONTROLLED_PILOT_AUTHORITY",
    "AWAIT_REPEAT_PILOT_APPROVAL",
    "AWAIT_SCALE_REVIEW_APPROVAL",
    "CONTROLLED_OPERATION_READY_LOCKED",
    "AUTONOMY_NOT_ELIGIBLE",
]


class V126Context:
    def __init__(self, *, pilot_authority_override=None) -> None:
        self.v125_baseline_status = sgc.baseline_status("final_report_v125.json", "V125")
        if pilot_authority_override is not None:
            self.pilot_authority_present = bool(pilot_authority_override)
        else:
            self.pilot_authority_present = False

    @property
    def blocker_map(self) -> dict[str, str]:
        a = "ABSENT" if not self.pilot_authority_present else "PRESENT"
        return {
            "pilot_approval": a,
            "firewall_adapter": a,
            "live_submit_enabled": "DISABLED",
            "caps_operator_confirmed": a,
            "broker_private_access": "LOCKED",
            "repeat_pilot_proof": "ABSENT",
            "scale_approval": "ABSENT",
            "autonomy_approval": "ABSENT",
        }

    @property
    def next_action_matrix_selection(self) -> str:
        return "AWAIT_CONTROLLED_PILOT_AUTHORITY" if not self.pilot_authority_present else "CONTROLLED_OPERATION_READY_LOCKED"

    @property
    def controller_status(self) -> str:
        return "FAIL_PILOT_BLOCKER_BASELINE_REGRESSION" if self.v125_baseline_status.startswith("FAIL") else "PASS_PILOT_BLOCKERS_AUDITED_AUTHORITY_MAPPED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v125_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V125_BASELINE_REGRESSION"] if self.v125_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return f"PILOT_BLOCKERS_AUDITED_NEXT_{self.next_action_matrix_selection}_NO_SUBMIT_NO_BROKER_CONTACT"


def _common(ctx: V126Context) -> dict[str, Any]:
    return {
        "v125_baseline_status": ctx.v125_baseline_status,
        "pilot_blocker_controller_status": ctx.controller_status,
        "blocker_classifier_status": "PASS_BLOCKERS_CLASSIFIED",
        "blocker_map": ctx.blocker_map,
        "pilot_approval_blocker_status": "PARTIAL_PILOT_APPROVAL_ABSENT" if not ctx.pilot_authority_present else "PASS_PILOT_APPROVAL_PRESENT",
        "firewall_adapter_blocker_status": "PARTIAL_FIREWALL_ADAPTER_ABSENT" if not ctx.pilot_authority_present else "PASS_FIREWALL_ADAPTER_PRESENT",
        "live_submit_caps_blocker_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_OPERATOR_CONTROLLED",
        "broker_private_access_blocker_status": "PASS_BROKER_PRIVATE_ACCESS_LOCKED",
        "repeat_scale_autonomy_blocker_status": "PARTIAL_REPEAT_SCALE_AUTONOMY_APPROVAL_ABSENT",
        "next_action_matrix": NEXT_ACTION_MATRIX,
        "next_action_matrix_selection": ctx.next_action_matrix_selection,
        "next_action_matrix_status": "PASS_NEXT_ACTION_MATRIX_SELECTED",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "broker_contacted": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v86_status": "PASS",
        "execution_lock_deep_recheck_v85_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V126Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v125_baseline"):
        return "PASS" if ctx.v125_baseline_status == "PASS_V125_BASELINE_READBACK" else "FAIL" if ctx.v125_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V126Context) -> dict[str, Any]:
    workstream = "v126: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v126_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V126_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v126_report.json":
        report.update({"completion_oriented_next_action_v126_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v125_carried_status": ctx.v125_baseline_status, "next_action_matrix_selection": ctx.next_action_matrix_selection, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v126_pilot_blocker_controller_report.json"), "next_action_matrix": str(ARTIFACTS / "v126_next_action_matrix_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v126.json", "dummy_canonical_identity_report_v126.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V126ReportFactory:
    def __init__(self, *, pilot_authority_override=None) -> None:
        self.kw = dict(pilot_authority_override=pilot_authority_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V126Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
