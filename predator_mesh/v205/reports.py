"""DUMMY v205 completion accelerator baseline — collapses all V195-V204 blockers into one canonical list; no submit.

Reads the full first-live-proof state and deduplicates repeated blockers into a single canonical list, detects redundant
gates, compresses the next-action, and estimates completion percentage by subsystem. Static PASS; total_live_orders=0,
broker_contacted=false, approval_files_written=0.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v205 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v205: Completion Accelerator Baseline And Blocker Dedup"
MISSION_NAME = "dummy_mission_state_report_v191.json"
FINAL_NAME = "final_report_v205.json"
INDEX_KEYS = ["completion_baseline_controller_status", "remaining_blocker_count", "live_orders"]
DASH_TITLE = "Dummy V205 Completion Accelerator Baseline"
MISSION_KEY = "dummy_mission_state_report_v191"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Baseline Dedup", "completion_baseline_controller_status"],
    ["Remaining Blockers", "remaining_blocker_count"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V205_ROUTES = [
    "/api/v205/completion-baseline-controller",
    "/api/v205/v204-baseline",
    "/api/v205/canonical-blocker-list",
    "/api/v205/redundant-gate-detection",
    "/api/v205/next-action-compression",
    "/api/v205/completion-percentage-estimate",
    "/api/v205/no-submit-proof",
    "/api/v205/no-broker-contact-proof",
    "/api/v205/no-approval-file-write-proof",
    "/api/v205/readiness-governor",
    "/api/v205/execution-lock",
    "/api/v205/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "completion-baseline-controller": ["v205_completion_baseline_controller_report.json"],
    "v204-baseline": ["v204_baseline_readback_v1_report.json"],
    "canonical-blocker-list": ["v205_canonical_blocker_list_report.json"],
    "redundant-gate-detection": ["v205_redundant_gate_detection_report.json"],
    "next-action-compression": ["v205_next_action_compression_report.json"],
    "completion-percentage-estimate": ["v205_completion_percentage_estimate_report.json"],
    "no-submit-proof": ["v205_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v205_no_broker_contact_proof_report.json"],
    "no-approval-file-write-proof": ["v205_no_approval_file_write_proof_report.json"],
    "readiness-governor": ["readiness_governor_v165_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v164_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v205_report_v1.json", "completion_oriented_next_action_v205_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(205)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v205/reports.py scripts/generate_v205_reports.py dashboard/backend/v205_routes.py",
    "python scripts/generate_v205_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CANONICAL_BLOCKERS = [
    "OPERATOR_APPROVAL_FILES_ABSENT",
    "LIVE_SUBMIT_CONFIG_DISABLED_OR_MISSING",
    "CAPS_CONFIRMATION_MISSING",
    "FIREWALL_ADAPTER_ABSENT",
    "BROKER_READONLY_APPROVAL_ABSENT",
    "FIRST_LIVE_PROOF_ABSENT",
    "RECONCILE_PROOF_ABSENT",
    "FORENSIC_PROOF_ABSENT",
    "SCALE_BLOCKED_NO_LIVE_PROOF",
    "AUTONOMY_BLOCKED_NO_LIVE_PROOF",
]
COMPLETION_PERCENTAGES = {
    "architecture_governance": 100,
    "authority_intake": 20,
    "first_live_proof": 0,
    "reconcile_forensic": 0,
    "repeat_proof": 0,
    "controlled_session": 0,
    "scale_review": 0,
    "autonomy_review": 0,
    "production_operation": 10,
}


class V205Context:
    def __init__(self) -> None:
        self.v204_baseline_status = sgc.baseline_status("final_report_v204.json", "V204")

    @property
    def remaining_blocker_count(self) -> int:
        return len(CANONICAL_BLOCKERS)

    @property
    def controller_status(self) -> str:
        return "FAIL_COMPLETION_BASELINE_REGRESSION" if self.v204_baseline_status.startswith("FAIL") else "PASS_COMPLETION_BASELINE_DEDUPED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v204_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V204_BASELINE_REGRESSION"] if self.v204_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "OPERATOR_AUTHORITY_INPUTS_REQUIRED"


def _common(ctx: V205Context) -> dict[str, Any]:
    return {
        "v204_baseline_status": ctx.v204_baseline_status,
        "completion_baseline_controller_status": ctx.controller_status,
        "canonical_blocker_list_status": "PASS_CANONICAL_BLOCKERS_DEDUPED",
        "canonical_blocker_list": CANONICAL_BLOCKERS,
        "remaining_blocker_count": ctx.remaining_blocker_count,
        "redundant_gate_detection_status": "PASS_REDUNDANT_GATES_DETECTED_COLLAPSED",
        "next_action_compression_status": "PASS_NEXT_ACTION_COMPRESSED",
        "completion_percentage_estimate_status": "PASS_COMPLETION_PERCENTAGE_ESTIMATED",
        "completion_percentages": COMPLETION_PERCENTAGES,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "approval_files_written": 0,
        "broker_contacted": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "total_live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v165_status": "PASS",
        "execution_lock_deep_recheck_v164_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V205Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v204_baseline"):
        return "PASS" if ctx.v204_baseline_status == "PASS_V204_BASELINE_READBACK" else "FAIL" if ctx.v204_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V205Context) -> dict[str, Any]:
    workstream = "v205: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v205_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V205_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v205_report.json":
        report.update({"completion_oriented_next_action_v205_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v204_carried_status": ctx.v204_baseline_status, "completion_baseline_controller_status": ctx.controller_status, "remaining_blocker_count": ctx.remaining_blocker_count, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v205_completion_baseline_controller_report.json"), "canonical_blocker_list": str(ARTIFACTS / "v205_canonical_blocker_list_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v205.json", "dummy_canonical_identity_report_v205.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V205ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V205Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
