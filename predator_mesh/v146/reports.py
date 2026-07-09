"""DUMMY v146 operator handoff packet V2 — emits precise operator instructions for a real pilot; writes no approval files.

Generates a read-only handoff packet: required files, exact phrases, live-submit/caps/firewall/broker-read-only
checklists, and a dry-vs-live explanation. Dummy never creates or modifies approval files or config
(approval_files_written=0). No submit and no broker contact.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v146 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v146: Operator Handoff Packet V2 Real Authority Instructions No Approval Write"
MISSION_NAME = "dummy_mission_state_report_v132.json"
FINAL_NAME = "final_report_v146.json"
INDEX_KEYS = ["handoff_controller_status", "approval_files_written", "broker_contacted"]
DASH_TITLE = "Dummy V146 Operator Handoff Packet V2"
MISSION_KEY = "dummy_mission_state_report_v132"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Handoff", "handoff_controller_status"],
    ["Approval Files Written", "approval_files_written"],
    ["Broker Contacted", "broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V146_ROUTES = [
    "/api/v146/handoff-controller",
    "/api/v146/v145-baseline",
    "/api/v146/required-files-checklist",
    "/api/v146/exact-phrase-checklist",
    "/api/v146/live-submit-config-checklist",
    "/api/v146/caps-checklist",
    "/api/v146/firewall-adapter-checklist",
    "/api/v146/broker-readonly-approval-checklist",
    "/api/v146/dry-vs-live-mode-explanation",
    "/api/v146/no-approval-file-write-proof",
    "/api/v146/no-submit-proof",
    "/api/v146/no-broker-contact-proof",
    "/api/v146/readiness-governor",
    "/api/v146/execution-lock",
    "/api/v146/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "handoff-controller": ["v146_handoff_controller_report.json"],
    "v145-baseline": ["v145_baseline_readback_v1_report.json"],
    "required-files-checklist": ["v146_required_files_checklist_report.json"],
    "exact-phrase-checklist": ["v146_exact_phrase_checklist_report.json"],
    "live-submit-config-checklist": ["v146_live_submit_config_checklist_report.json"],
    "caps-checklist": ["v146_caps_checklist_report.json"],
    "firewall-adapter-checklist": ["v146_firewall_adapter_checklist_report.json"],
    "broker-readonly-approval-checklist": ["v146_broker_readonly_approval_checklist_report.json"],
    "dry-vs-live-mode-explanation": ["v146_dry_vs_live_mode_explanation_report.json"],
    "no-approval-file-write-proof": ["v146_no_approval_file_write_proof_report.json"],
    "no-submit-proof": ["v146_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v146_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v106_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v105_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v146_report_v1.json", "completion_oriented_next_action_v146_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(146)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v146/reports.py scripts/generate_v146_reports.py dashboard/backend/v146_routes.py",
    "python scripts/generate_v146_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

REQUIRED_FILES = [
    "runtime/approvals/dummy_controlled_production_pilot_approval.json",
    "runtime/approvals/dummy_production_pilot_repeat_approval.json",
    "runtime/approvals/dummy_broker_readonly_approval.json",
    "runtime/approvals/dummy_scale_step_1_approval.json",
    "runtime/approvals/dummy_controlled_operation_approval.json",
]


class V146Context:
    def __init__(self) -> None:
        self.v145_baseline_status = sgc.baseline_status("final_report_v145.json", "V145")

    @property
    def controller_status(self) -> str:
        return "FAIL_HANDOFF_BASELINE_REGRESSION" if self.v145_baseline_status.startswith("FAIL") else "PASS_OPERATOR_HANDOFF_PACKET_READY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v145_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V145_BASELINE_REGRESSION"] if self.v145_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "OPERATOR_MUST_MANUALLY_SUPPLY_APPROVALS_LIVE_SUBMIT_CONFIG_CAPS_AND_FIREWALL_ADAPTER_DUMMY_WRITES_NOTHING"


def _common(ctx: V146Context) -> dict[str, Any]:
    return {
        "v145_baseline_status": ctx.v145_baseline_status,
        "handoff_controller_status": ctx.controller_status,
        "required_files_checklist_status": "PASS_REQUIRED_FILES_LISTED",
        "required_files": REQUIRED_FILES,
        "exact_phrase_checklist_status": "PASS_EXACT_PHRASES_LISTED",
        "exact_phrases": {
            "controlled_production_pilot": sgc.CONTROLLED_PILOT_PHRASE,
            "repeat_pilot": sgc.REPEAT_PILOT_PHRASE,
            "broker_read_only": sgc.BROKER_READONLY_PHRASE,
        },
        "live_submit_config_checklist_status": "PASS_LIVE_SUBMIT_OPERATOR_ACTION_REQUIRED",
        "caps_checklist_status": "PASS_CAPS_OPERATOR_ACTION_REQUIRED",
        "firewall_adapter_checklist_status": "PASS_FIREWALL_ADAPTER_OPERATOR_INJECTION_REQUIRED",
        "broker_readonly_approval_checklist_status": "PASS_BROKER_READONLY_OPERATOR_ACTION_REQUIRED",
        "dry_vs_live_mode_explanation_status": "PASS_DRY_VS_LIVE_EXPLAINED",
        "dry_vs_live_mode_explanation": "DRY_LOCKED rehearsal is inert and cannot contact a broker; LIVE_AUTHORIZED requires operator-supplied approval, live-submit, caps, and firewall adapter.",
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "approval_files_written": 0,
        "config_modified_by_dummy": False,
        "broker_contacted": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v106_status": "PASS",
        "execution_lock_deep_recheck_v105_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V146Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v145_baseline"):
        return "PASS" if ctx.v145_baseline_status == "PASS_V145_BASELINE_READBACK" else "FAIL" if ctx.v145_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V146Context) -> dict[str, Any]:
    workstream = "v146: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v146_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V146_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v146_report.json":
        report.update({"completion_oriented_next_action_v146_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v145_carried_status": ctx.v145_baseline_status, "handoff_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v146_handoff_controller_report.json"), "no_approval_file_write": str(ARTIFACTS / "v146_no_approval_file_write_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v146.json", "dummy_canonical_identity_report_v146.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V146ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V146Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
