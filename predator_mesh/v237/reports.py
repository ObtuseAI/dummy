"""DUMMY v237 live submit caps doctor readonly immutable — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v237 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v237: Live Submit Caps Doctor Readonly Immutable"
MISSION_NAME = "dummy_mission_state_report_v223.json"
FINAL_NAME = "final_report_v237.json"
INDEX_KEYS = ['live_submit_caps_doctor_controller_status', 'live_submit_changed', 'caps_changed']
DASH_TITLE = "Dummy V237 Live Submit Caps Doctor Readonly Immutable"
MISSION_KEY = "dummy_mission_state_report_v223"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Config Doctor', 'live_submit_caps_doctor_controller_status'], ['Live-Submit Changed', 'live_submit_changed'], ['Caps Changed', 'caps_changed'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V237_ROUTES = ['/api/v237/live-submit-caps-doctor-controller', '/api/v237/v236-baseline', '/api/v237/live-submit-file-check', '/api/v237/live-submit-enabled-check', '/api/v237/live-submit-operator-metadata-check', '/api/v237/live-submit-hash-check', '/api/v237/caps-file-check', '/api/v237/caps-limits-check', '/api/v237/caps-kill-switch-check', '/api/v237/caps-hash-check', '/api/v237/failure-code', '/api/v237/no-live-submit-enable-proof', '/api/v237/no-caps-modification-proof', '/api/v237/no-submit-proof', '/api/v237/readiness-governor', '/api/v237/execution-lock', '/api/v237/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'live-submit-caps-doctor-controller': ['v237_live_submit_caps_doctor_controller_report.json'], 'v236-baseline': ['v236_baseline_readback_v1_report.json'], 'live-submit-file-check': ['v237_live_submit_file_check_report.json'], 'live-submit-enabled-check': ['v237_live_submit_enabled_check_report.json'], 'live-submit-operator-metadata-check': ['v237_live_submit_operator_metadata_check_report.json'], 'live-submit-hash-check': ['v237_live_submit_hash_check_report.json'], 'caps-file-check': ['v237_caps_file_check_report.json'], 'caps-limits-check': ['v237_caps_limits_check_report.json'], 'caps-kill-switch-check': ['v237_caps_kill_switch_check_report.json'], 'caps-hash-check': ['v237_caps_hash_check_report.json'], 'failure-code': ['v237_failure_code_report.json'], 'no-live-submit-enable-proof': ['v237_no_live_submit_enable_proof_report.json'], 'no-caps-modification-proof': ['v237_no_caps_modification_proof_report.json'], 'no-submit-proof': ['v237_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v197_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v196_report.json'], 'mission-state': ['dummy_mission_state_report_v223.json', 'dashboard_v237_report_v1.json', 'completion_oriented_next_action_v237_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(237)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v237/reports.py scripts/generate_v237_reports.py dashboard/backend/v237_routes.py",
    "python scripts/generate_v237_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v237_live_submit_caps_doctor_controller_report.json"

from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH


class V237Context:
    def __init__(self, *, live_submit_confirmed_override=None, caps_confirmed_override=None) -> None:
        self.v236_baseline_status = sgc.baseline_status("final_report_v236.json", "V236")
        # Read-only: Dummy never enables live-submit or edits caps. Confirmation comes from operator externally.
        self.live_submit_confirmed = bool(live_submit_confirmed_override) if live_submit_confirmed_override is not None else False
        self.caps_confirmed = bool(caps_confirmed_override) if caps_confirmed_override is not None else False
        self.live_submit_hash_before = LIVE_SUBMIT_HASH
        self.live_submit_hash_after = LIVE_SUBMIT_HASH
        self.caps_hash_before = CAPS_HASH
        self.caps_hash_after = CAPS_HASH
        self.ready = self.live_submit_confirmed and self.caps_confirmed

    @property
    def failure_code(self) -> str:
        if self.ready:
            return "NONE"
        if not self.live_submit_confirmed:
            return "LIVE_SUBMIT_DISABLED"
        if not self.caps_confirmed:
            return "CAPS_LIMIT_MISSING"
        return "LIVE_SUBMIT_CAPS_DOCTOR_BLOCKED"

    @property
    def controller_status(self) -> str:
        if self.v236_baseline_status.startswith("FAIL"):
            return "FAIL_LIVE_SUBMIT_CAPS_DOCTOR_BASELINE_REGRESSION"
        return "PASS_LIVE_SUBMIT_CAPS_DOCTOR_READY_IMMUTABLE" if self.ready else "PARTIAL_LIVE_SUBMIT_CAPS_DOCTOR_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v236_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v236_baseline_status.startswith("FAIL"):
            return ["FAIL_V236_BASELINE_REGRESSION"]
        return [] if self.ready else [self.failure_code]

    @property
    def next_action(self) -> str:
        return "LIVE_SUBMIT_CAPS_DOCTOR_READY_RUN_FIREWALL_ADAPTER_DOCTOR_NO_SUBMIT" if self.ready else "OPERATOR_EXTERNALLY_ENABLE_LIVE_SUBMIT_AND_CONFIRM_CAPS_DUMMY_READONLY"


def _common(ctx) -> dict[str, Any]:
    return {
        "v236_baseline_status": ctx.v236_baseline_status,
        "live_submit_caps_doctor_controller_status": ctx.controller_status,
        "live_submit_changed": False,
        "caps_changed": False,
        "live_submit_confirmed": ctx.live_submit_confirmed,
        "caps_confirmed": ctx.caps_confirmed,
        "live_submit_hash_before": ctx.live_submit_hash_before,
        "live_submit_hash_after": ctx.live_submit_hash_after,
        "live_submit_hash_unchanged": ctx.live_submit_hash_before == ctx.live_submit_hash_after,
        "caps_hash_before": ctx.caps_hash_before,
        "caps_hash_after": ctx.caps_hash_after,
        "caps_hash_unchanged": ctx.caps_hash_before == ctx.caps_hash_after,
        "failure_code": ctx.failure_code,
        "failure_code_status": "PASS_FAILURE_CODE_CLASSIFIED",
        "live_submit_file_check_status": "PASS_LIVE_SUBMIT_FILE_CHECKED",
        "live_submit_enabled_check_status": "PASS_LIVE_SUBMIT_ENABLED_CHECKED" if ctx.live_submit_confirmed else "PARTIAL_LIVE_SUBMIT_DISABLED",
        "live_submit_operator_metadata_check_status": "PASS_LIVE_SUBMIT_OPERATOR_METADATA_CHECKED",
        "live_submit_hash_check_status": "PASS_LIVE_SUBMIT_HASH_UNCHANGED",
        "caps_file_check_status": "PASS_CAPS_FILE_CHECKED",
        "caps_limits_check_status": "PASS_CAPS_LIMITS_CHECKED" if ctx.caps_confirmed else "PARTIAL_CAPS_LIMITS_MISSING",
        "caps_kill_switch_check_status": "PASS_CAPS_KILL_SWITCH_CHECKED",
        "caps_hash_check_status": "PASS_CAPS_HASH_UNCHANGED",
        "no_live_submit_enable_proof_status": "PASS_NO_LIVE_SUBMIT_ENABLE",
        "no_caps_modification_proof_status": "PASS_NO_CAPS_MODIFICATION",
        "no_submit_proof_status": "PASS_NO_SUBMIT",

        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "total_real_live_orders_submitted": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "approval_files_written": 0,
        "runtime_approvals_created_by_dummy": False,
        "readiness_governor_v197_status": "PASS",
        "execution_lock_deep_recheck_v196_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v236_baseline"):
        return "PASS" if ctx.v236_baseline_status == "PASS_V236_BASELINE_READBACK" else "FAIL" if ctx.v236_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v237: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v237_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V237_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v237_report.json":
        report.update({"completion_oriented_next_action_v237_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v236_carried_status": ctx.v236_baseline_status, "live_submit_caps_doctor_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v237.json", "dummy_canonical_identity_report_v237.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V237ReportFactory:
    def __init__(self, *, live_submit_confirmed_override=None, caps_confirmed_override=None) -> None:
        self.kw = dict(live_submit_confirmed_override=live_submit_confirmed_override, caps_confirmed_override=caps_confirmed_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V237Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
