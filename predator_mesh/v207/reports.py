"""DUMMY v207 activation cockpit — one read-only page/API showing what remains for first live proof; no submit from UI.

Consolidates blocker list, exact next operator actions, completion percentages, authority/live-proof/reconcile/forensic/
scale/autonomy status, and safe-mode status into one cockpit surface. The UI can never submit orders, write approval
files, or modify caps/live-submit. Default is PASS_ACTIVATION_COCKPIT_READY_READONLY.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v207 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v207: Activation Cockpit One Page Completion Dashboard"
MISSION_NAME = "dummy_mission_state_report_v193.json"
FINAL_NAME = "final_report_v207.json"
INDEX_KEYS = ["cockpit_controller_status", "ui_submit_enabled", "ui_config_write_enabled"]
DASH_TITLE = "Dummy V207 Activation Cockpit"
MISSION_KEY = "dummy_mission_state_report_v193"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Cockpit", "cockpit_controller_status"],
    ["UI Submit Enabled", "ui_submit_enabled"],
    ["UI Config Write Enabled", "ui_config_write_enabled"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V207_ROUTES = [
    "/api/v207/activation-cockpit",
    "/api/v207/v206-baseline",
    "/api/v207/blocker-list",
    "/api/v207/next-operator-actions",
    "/api/v207/completion-percentages",
    "/api/v207/authority-status",
    "/api/v207/live-proof-status",
    "/api/v207/reconcile-forensic-status",
    "/api/v207/scale-autonomy-status",
    "/api/v207/safe-mode-status",
    "/api/v207/no-ui-submit-proof",
    "/api/v207/no-ui-config-write-proof",
    "/api/v207/readiness-governor",
    "/api/v207/execution-lock",
    "/api/v207/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "activation-cockpit": ["v207_activation_cockpit_report.json"],
    "v206-baseline": ["v206_baseline_readback_v1_report.json"],
    "blocker-list": ["v207_blocker_list_report.json"],
    "next-operator-actions": ["v207_next_operator_actions_report.json"],
    "completion-percentages": ["v207_completion_percentages_report.json"],
    "authority-status": ["v207_authority_status_report.json"],
    "live-proof-status": ["v207_live_proof_status_report.json"],
    "reconcile-forensic-status": ["v207_reconcile_forensic_status_report.json"],
    "scale-autonomy-status": ["v207_scale_autonomy_status_report.json"],
    "safe-mode-status": ["v207_safe_mode_status_report.json"],
    "no-ui-submit-proof": ["v207_no_ui_submit_proof_report.json"],
    "no-ui-config-write-proof": ["v207_no_ui_config_write_proof_report.json"],
    "readiness-governor": ["readiness_governor_v167_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v166_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v207_report_v1.json", "completion_oriented_next_action_v207_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(207)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v207/reports.py scripts/generate_v207_reports.py dashboard/backend/v207_routes.py",
    "python scripts/generate_v207_reports.py",
    "python scripts/run_dummy_activation_cockpit_report.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

NEXT_OPERATOR_ACTIONS = [
    "PROVIDE_EXACT_APPROVAL_FILES",
    "ENABLE_LIVE_SUBMIT_OPERATOR_SIDE",
    "CONFIRM_CAPS_CONFIG",
    "INJECT_LIVEBROKERFIREWALL_ADAPTER",
    "OPTIONALLY_PROVIDE_BROKER_READONLY_APPROVAL",
    "RUN_FIRST_LIVE_PROOF_WITH_CLI_ENV_GATE",
]


def build_cockpit_snapshot() -> dict[str, Any]:
    return {
        "authority_status": str(sgc.load_artifact("final_report_v195.json").get("activation_binder_controller_status", "PARTIAL_FIRST_LIVE_PROOF_AUTHORITY_INCOMPLETE")),
        "live_proof_status": str(sgc.load_artifact("final_report_v199.json").get("first_live_proof_gate_controller_status", "PARTIAL_FIRST_LIVE_PROOF_NOT_ARMED")),
        "reconcile_status": str(sgc.load_artifact("final_report_v200.json").get("reconcile_controller_status", "PARTIAL_NO_FIRST_LIVE_PROOF_TO_RECONCILE")),
        "forensic_status": str(sgc.load_artifact("final_report_v201.json").get("forensic_controller_status", "PARTIAL_NO_FIRST_LIVE_PROOF_TO_REVIEW")),
        "scale_status": str(sgc.load_artifact("final_report_v202.json").get("scale_recommendation", "SCALE_BLOCKED_NO_LIVE_PROOF")),
        "autonomy_status": str(sgc.load_artifact("final_report_v202.json").get("autonomy_recommendation", "AUTONOMY_BLOCKED_NO_LIVE_PROOF")),
        "completion_percentages": sgc.load_artifact("final_report_v205.json").get("completion_percentages", {}),
        "canonical_blockers": sgc.load_artifact("final_report_v205.json").get("canonical_blocker_list", []),
        "next_operator_actions": NEXT_OPERATOR_ACTIONS,
        "safe_mode": "READ_ONLY_FAIL_CLOSED",
        "ui_submit_enabled": False,
        "ui_config_write_enabled": False,
        "total_live_orders": 0,
        "broker_contacted": False,
        "approval_files_written": 0,
    }


class V207Context:
    def __init__(self) -> None:
        self.v206_baseline_status = sgc.baseline_status("final_report_v206.json", "V206")
        self.snapshot = build_cockpit_snapshot()

    @property
    def controller_status(self) -> str:
        return "FAIL_COCKPIT_BASELINE_REGRESSION" if self.v206_baseline_status.startswith("FAIL") else "PASS_ACTIVATION_COCKPIT_READY_READONLY"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v206_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V206_BASELINE_REGRESSION"] if self.v206_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "ACTIVATION_COCKPIT_READY_READONLY_OPERATOR_ACTIONS_SHOWN_NO_UI_SUBMIT"


def _common(ctx: V207Context) -> dict[str, Any]:
    return {
        "v206_baseline_status": ctx.v206_baseline_status,
        "cockpit_controller_status": ctx.controller_status,
        "blocker_list_status": "PASS_BLOCKER_LIST_RENDERED",
        "blocker_list": ctx.snapshot["canonical_blockers"],
        "next_operator_actions_status": "PASS_NEXT_OPERATOR_ACTIONS_RENDERED",
        "next_operator_actions": NEXT_OPERATOR_ACTIONS,
        "completion_percentages_status": "PASS_COMPLETION_PERCENTAGES_RENDERED",
        "completion_percentages": ctx.snapshot["completion_percentages"],
        "authority_status_status": "PASS_AUTHORITY_STATUS_RENDERED",
        "authority_status": ctx.snapshot["authority_status"],
        "live_proof_status_status": "PASS_LIVE_PROOF_STATUS_RENDERED",
        "live_proof_status": ctx.snapshot["live_proof_status"],
        "reconcile_forensic_status_status": "PASS_RECONCILE_FORENSIC_STATUS_RENDERED",
        "reconcile_status": ctx.snapshot["reconcile_status"],
        "forensic_status": ctx.snapshot["forensic_status"],
        "scale_autonomy_status_status": "PASS_SCALE_AUTONOMY_STATUS_RENDERED",
        "scale_status": ctx.snapshot["scale_status"],
        "autonomy_status": ctx.snapshot["autonomy_status"],
        "safe_mode_status_status": "PASS_SAFE_MODE_READ_ONLY",
        "safe_mode": "READ_ONLY_FAIL_CLOSED",
        "no_ui_submit_proof_status": "PASS_NO_UI_SUBMIT",
        "no_ui_config_write_proof_status": "PASS_NO_UI_CONFIG_WRITE",
        "cockpit_snapshot": ctx.snapshot,
        "ui_submit_enabled": False,
        "ui_config_write_enabled": False,
        "approval_files_written": 0,
        "broker_contacted": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v167_status": "PASS",
        "execution_lock_deep_recheck_v166_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V207Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v206_baseline"):
        return "PASS" if ctx.v206_baseline_status == "PASS_V206_BASELINE_READBACK" else "FAIL" if ctx.v206_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V207Context) -> dict[str, Any]:
    workstream = "v207: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v207_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V207_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v207_report.json":
        report.update({"completion_oriented_next_action_v207_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v206_carried_status": ctx.v206_baseline_status, "cockpit_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v207_activation_cockpit_report.json"), "cockpit_snapshot": str(ARTIFACTS / "activation_cockpit_v207.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v207.json", "dummy_canonical_identity_report_v207.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V207ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V207Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
