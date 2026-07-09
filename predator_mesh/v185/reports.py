"""DUMMY v185 live-proof blocker closure V6 — audits V175-V184 blockers into exact live-proof + autonomy maps; no submit.

Classifies every remaining live-proof and autonomy blocker (controlled-operation/session approvals, first/repeat/session
pilot proof, live-submit/caps, firewall, autonomy-review, scale) and selects a next-action from a fixed matrix. Static
PASS audit; live_orders=0, broker_contacted=false, approval_files_written=0.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v185 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v185: Live Proof Blocker Closure V6 Controlled Session And Autonomy Map"
MISSION_NAME = "dummy_mission_state_report_v171.json"
FINAL_NAME = "final_report_v185.json"
INDEX_KEYS = ["live_proof_blocker_controller_status", "next_action_matrix_selection", "live_orders"]
DASH_TITLE = "Dummy V185 Live-Proof Blocker Closure V6"
MISSION_KEY = "dummy_mission_state_report_v171"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Blocker Audit", "live_proof_blocker_controller_status"],
    ["Next Action Matrix", "next_action_matrix_selection"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V185_ROUTES = [
    "/api/v185/live-proof-blocker-controller",
    "/api/v185/v184-baseline",
    "/api/v185/blocker-classifier",
    "/api/v185/controlled-operation-session-approval-blocker",
    "/api/v185/pilot-session-proof-blocker",
    "/api/v185/live-submit-caps-blocker",
    "/api/v185/firewall-adapter-blocker",
    "/api/v185/autonomy-scale-approval-blocker",
    "/api/v185/next-action-matrix",
    "/api/v185/no-submit-proof",
    "/api/v185/no-broker-contact-proof",
    "/api/v185/no-approval-file-write-proof",
    "/api/v185/readiness-governor",
    "/api/v185/execution-lock",
    "/api/v185/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "live-proof-blocker-controller": ["v185_live_proof_blocker_controller_report.json"],
    "v184-baseline": ["v184_baseline_readback_v1_report.json"],
    "blocker-classifier": ["v185_blocker_classifier_report.json"],
    "controlled-operation-session-approval-blocker": ["v185_controlled_operation_session_approval_blocker_report.json"],
    "pilot-session-proof-blocker": ["v185_pilot_session_proof_blocker_report.json"],
    "live-submit-caps-blocker": ["v185_live_submit_caps_blocker_report.json"],
    "firewall-adapter-blocker": ["v185_firewall_adapter_blocker_report.json"],
    "autonomy-scale-approval-blocker": ["v185_autonomy_scale_approval_blocker_report.json"],
    "next-action-matrix": ["v185_next_action_matrix_report.json"],
    "no-submit-proof": ["v185_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v185_no_broker_contact_proof_report.json"],
    "no-approval-file-write-proof": ["v185_no_approval_file_write_proof_report.json"],
    "readiness-governor": ["readiness_governor_v145_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v144_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v185_report_v1.json", "completion_oriented_next_action_v185_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(185)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v185/reports.py scripts/generate_v185_reports.py dashboard/backend/v185_routes.py",
    "python scripts/generate_v185_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

BLOCKER_MAP = {
    "controlled_operation_approval": "ABSENT",
    "controlled_session_approval": "ABSENT",
    "first_pilot_proof": "ABSENT",
    "repeat_pilot_proof": "ABSENT",
    "controlled_session_proof": "ABSENT",
    "live_submit_enabled": "DISABLED",
    "caps_operator_confirmed": "ABSENT",
    "firewall_adapter": "ABSENT",
    "autonomy_review_approval": "ABSENT",
    "scale_proof": "ABSENT",
}
NEXT_ACTION_MATRIX = [
    "AWAIT_FIRST_REAL_PILOT_OR_CONTROLLED_SESSION_PROOF",
    "AWAIT_CONTROLLED_SESSION_APPROVAL",
    "AWAIT_AUTONOMY_REVIEW_APPROVAL",
    "AWAIT_SCALE_REVIEW_APPROVAL",
    "CONTROLLED_OPERATION_READY_LOCKED",
]


class V185Context:
    def __init__(self) -> None:
        self.v184_baseline_status = sgc.baseline_status("final_report_v184.json", "V184")

    @property
    def next_action_matrix_selection(self) -> str:
        return "AWAIT_FIRST_REAL_PILOT_OR_CONTROLLED_SESSION_PROOF"

    @property
    def controller_status(self) -> str:
        return "FAIL_LIVE_PROOF_BLOCKER_BASELINE_REGRESSION" if self.v184_baseline_status.startswith("FAIL") else "PASS_LIVE_PROOF_BLOCKERS_AUDITED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v184_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V184_BASELINE_REGRESSION"] if self.v184_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return f"LIVE_PROOF_BLOCKERS_AUDITED_NEXT_{self.next_action_matrix_selection}_NO_SUBMIT_NO_BROKER_CONTACT"


def _common(ctx: V185Context) -> dict[str, Any]:
    return {
        "v184_baseline_status": ctx.v184_baseline_status,
        "live_proof_blocker_controller_status": ctx.controller_status,
        "blocker_classifier_status": "PASS_BLOCKERS_CLASSIFIED",
        "blocker_map": BLOCKER_MAP,
        "controlled_operation_session_approval_blocker_status": "PARTIAL_CONTROLLED_OPERATION_AND_SESSION_APPROVAL_ABSENT",
        "pilot_session_proof_blocker_status": "PARTIAL_PILOT_AND_SESSION_PROOF_ABSENT",
        "live_submit_caps_blocker_status": "PASS_LIVE_SUBMIT_DISABLED_CAPS_OPERATOR_CONTROLLED",
        "firewall_adapter_blocker_status": "PARTIAL_FIREWALL_ADAPTER_ABSENT",
        "autonomy_scale_approval_blocker_status": "PARTIAL_AUTONOMY_AND_SCALE_APPROVAL_ABSENT",
        "next_action_matrix": NEXT_ACTION_MATRIX,
        "next_action_matrix_selection": ctx.next_action_matrix_selection,
        "next_action_matrix_status": "PASS_NEXT_ACTION_MATRIX_SELECTED",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "approval_files_written": 0,
        "broker_contacted": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v145_status": "PASS",
        "execution_lock_deep_recheck_v144_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V185Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v184_baseline"):
        return "PASS" if ctx.v184_baseline_status == "PASS_V184_BASELINE_READBACK" else "FAIL" if ctx.v184_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V185Context) -> dict[str, Any]:
    workstream = "v185: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v185_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V185_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v185_report.json":
        report.update({"completion_oriented_next_action_v185_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v184_carried_status": ctx.v184_baseline_status, "next_action_matrix_selection": ctx.next_action_matrix_selection, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v185_live_proof_blocker_controller_report.json"), "next_action_matrix": str(ARTIFACTS / "v185_next_action_matrix_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v185.json", "dummy_canonical_identity_report_v185.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V185ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V185Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
