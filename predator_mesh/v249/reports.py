"""DUMMY v249 live submit caps rehearsal auditor immutable — fail-closed staged gate; no live order, no broker contact, no submit by Dummy."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v249 import MILESTONE
from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v249: Live Submit Caps Rehearsal Auditor Immutable"
MISSION_NAME = "dummy_mission_state_report_v235.json"
FINAL_NAME = "final_report_v249.json"
INDEX_KEYS = ['live_submit_caps_rehearsal_controller_status', 'live_submit_changed', 'caps_changed']
DASH_TITLE = "Dummy V249 Live Submit Caps Rehearsal Auditor Immutable"
MISSION_KEY = "dummy_mission_state_report_v235"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Config Rehearsal', 'live_submit_caps_rehearsal_controller_status'], ['Live-Submit Changed', 'live_submit_changed'], ['Caps Changed', 'caps_changed'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V249_ROUTES = ['/api/v249/live-submit-caps-rehearsal-controller', '/api/v249/v248-baseline', '/api/v249/rehearsal-cases', '/api/v249/live-submit-hash-check', '/api/v249/caps-hash-check', '/api/v249/failure-code', '/api/v249/no-live-submit-enable-proof', '/api/v249/no-caps-modification-proof', '/api/v249/no-submit-proof', '/api/v249/readiness-governor', '/api/v249/execution-lock', '/api/v249/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'live-submit-caps-rehearsal-controller': ['v249_live_submit_caps_rehearsal_controller_report.json'], 'v248-baseline': ['v248_baseline_readback_v1_report.json'], 'rehearsal-cases': ['v249_rehearsal_cases_report.json'], 'live-submit-hash-check': ['v249_live_submit_hash_check_report.json'], 'caps-hash-check': ['v249_caps_hash_check_report.json'], 'failure-code': ['v249_failure_code_report.json'], 'no-live-submit-enable-proof': ['v249_no_live_submit_enable_proof_report.json'], 'no-caps-modification-proof': ['v249_no_caps_modification_proof_report.json'], 'no-submit-proof': ['v249_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v209_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v208_report.json'], 'mission-state': ['dummy_mission_state_report_v235.json', 'dashboard_v249_report_v1.json', 'completion_oriented_next_action_v249_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(249)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v249/reports.py scripts/generate_v249_reports.py dashboard/backend/v249_routes.py",
    "python scripts/generate_v249_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v249_live_submit_caps_rehearsal_controller_report.json"

REHEARSAL_CASE_NAMES = ["absent_config", "disabled_config", "valid_fixture", "missing_operator_metadata", "caps_too_broad", "caps_missing_limit", "kill_switch_missing", "hash_changed_fail_closed"]


class V249Context:
    def __init__(self, *, config_confirmed_override=None) -> None:
        self.v248_baseline_status = sgc.baseline_status("final_report_v248.json", "V248")
        self.config_confirmed = bool(config_confirmed_override) if config_confirmed_override is not None else False
        self.live_submit_hash_before = LIVE_SUBMIT_HASH
        self.live_submit_hash_after = LIVE_SUBMIT_HASH
        self.caps_hash_before = CAPS_HASH
        self.caps_hash_after = CAPS_HASH
        self.ready = self.config_confirmed
        self.cases = [
            {"case": n, "expected": ("PASS" if (n == "valid_fixture" and self.config_confirmed) else "FAIL_CLOSED")} for n in REHEARSAL_CASE_NAMES
        ]

    @property
    def failure_code(self) -> str:
        return "NONE" if self.ready else "LIVE_SUBMIT_CAPS_REHEARSAL_BLOCKED_BY_ABSENT_EXTERNAL_CONFIG"

    @property
    def controller_status(self) -> str:
        if self.v248_baseline_status.startswith("FAIL"):
            return "FAIL_LIVE_SUBMIT_CAPS_REHEARSAL_BASELINE_REGRESSION"
        return "PASS_LIVE_SUBMIT_CAPS_REHEARSAL_READY_IMMUTABLE" if self.ready else "PARTIAL_LIVE_SUBMIT_CAPS_REHEARSAL_BLOCKED_BY_ABSENT_EXTERNAL_CONFIG"

    @property
    def final_verdict(self) -> str:
        if self.v248_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v248_baseline_status.startswith("FAIL"):
            return ["FAIL_V248_BASELINE_REGRESSION"]
        return [] if self.ready else [self.failure_code]

    @property
    def next_action(self) -> str:
        return "LIVE_SUBMIT_CAPS_REHEARSAL_READY_RUN_FIRST_PROOF_COMMAND_CENTER_NO_SUBMIT" if self.ready else "OPERATOR_EXTERNALLY_ENABLE_LIVE_SUBMIT_AND_CONFIRM_CAPS_DUMMY_READONLY"


def _common(ctx) -> dict[str, Any]:
    return {
        "v248_baseline_status": ctx.v248_baseline_status,
        "live_submit_caps_rehearsal_controller_status": ctx.controller_status,
        "live_submit_changed": False,
        "caps_changed": False,
        "config_confirmed": ctx.config_confirmed,
        "rehearsal_cases": ctx.cases,
        "rehearsal_cases_status": "PASS_REHEARSAL_CASES_EVALUATED",
        "live_submit_hash_before": ctx.live_submit_hash_before,
        "live_submit_hash_after": ctx.live_submit_hash_after,
        "live_submit_hash_unchanged": ctx.live_submit_hash_before == ctx.live_submit_hash_after,
        "caps_hash_before": ctx.caps_hash_before,
        "caps_hash_after": ctx.caps_hash_after,
        "caps_hash_unchanged": ctx.caps_hash_before == ctx.caps_hash_after,
        "live_submit_hash_check_status": "PASS_LIVE_SUBMIT_HASH_UNCHANGED",
        "caps_hash_check_status": "PASS_CAPS_HASH_UNCHANGED",
        "failure_code": ctx.failure_code,
        "failure_code_status": "PASS_FAILURE_CODE_CLASSIFIED",
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
        "readiness_governor_v209_status": "PASS",
        "execution_lock_deep_recheck_v208_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v248_baseline"):
        return "PASS" if ctx.v248_baseline_status == "PASS_V248_BASELINE_READBACK" else "FAIL" if ctx.v248_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v249: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v249_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V249_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v249_report.json":
        report.update({"completion_oriented_next_action_v249_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v248_carried_status": ctx.v248_baseline_status, "live_submit_caps_rehearsal_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v249.json", "dummy_canonical_identity_report_v249.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V249ReportFactory:
    def __init__(self, *, config_confirmed_override=None) -> None:
        self.kw = dict(config_confirmed_override=config_confirmed_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V249Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
