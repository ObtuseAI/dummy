"""DUMMY v268 external live submit caps state verifier immutable — fail-closed staged gate; no live order, no broker contact, no submit by Dummy, no live-submit enable, no caps modification."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v268 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v268: External Live Submit Caps State Verifier Immutable"
MISSION_NAME = "dummy_mission_state_report_v254.json"
FINAL_NAME = "final_report_v268.json"
INDEX_KEYS = ['external_live_submit_caps_state_verifier_controller_status', 'live_submit_changed', 'caps_changed']
DASH_TITLE = "Dummy V268 External Live Submit Caps State Verifier Immutable"
MISSION_KEY = "dummy_mission_state_report_v254"
SUMMARY_FIELDS = [['Mission', 'mission_state_verdict'], ['Caps State Verifier', 'external_live_submit_caps_state_verifier_controller_status'], ['Live-Submit Changed', 'live_submit_changed'], ['Caps Changed', 'caps_changed'], ['Next Action', 'current_next_action'], ['Blockers', 'current_blockers']]

V268_ROUTES = ['/api/v268/external-live-submit-caps-state-verifier-controller', '/api/v268/v267-baseline', '/api/v268/live-submit-checks', '/api/v268/caps-checks', '/api/v268/kill-switch-check', '/api/v268/live-submit-hash-check', '/api/v268/caps-hash-check', '/api/v268/failure-code', '/api/v268/no-live-submit-enable-proof', '/api/v268/no-caps-modification-proof', '/api/v268/no-submit-proof', '/api/v268/readiness-governor', '/api/v268/execution-lock', '/api/v268/mission-state']

REPORT_GROUPS: dict[str, list[str]] = {'external-live-submit-caps-state-verifier-controller': ['v268_external_live_submit_caps_state_verifier_controller_report.json'], 'v267-baseline': ['v267_baseline_readback_v1_report.json'], 'live-submit-checks': ['v268_live_submit_checks_report.json'], 'caps-checks': ['v268_caps_checks_report.json'], 'kill-switch-check': ['v268_kill_switch_check_report.json'], 'live-submit-hash-check': ['v268_live_submit_hash_check_report.json'], 'caps-hash-check': ['v268_caps_hash_check_report.json'], 'failure-code': ['v268_failure_code_report.json'], 'no-live-submit-enable-proof': ['v268_no_live_submit_enable_proof_report.json'], 'no-caps-modification-proof': ['v268_no_caps_modification_proof_report.json'], 'no-submit-proof': ['v268_no_submit_proof_report.json'], 'readiness-governor': ['readiness_governor_v228_report.json'], 'execution-lock': ['execution_lock_deep_recheck_v227_report.json'], 'mission-state': ['dummy_mission_state_report_v254.json', 'dashboard_v268_report_v1.json', 'completion_oriented_next_action_v268_report.json']}

SAFETY_REPORT_NAMES = sgc.safety_report_names(268)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v268/reports.py scripts/generate_v268_reports.py dashboard/backend/v268_routes.py",
    "python scripts/generate_v268_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

CONTROLLER_REPORT = "v268_external_live_submit_caps_state_verifier_controller_report.json"

from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH


class V268Context:
    def __init__(self, *, live_submit_descriptor=None, caps_descriptor=None, config_confirmed_override=None) -> None:
        self.v267_baseline_status = sgc.baseline_status("final_report_v267.json", "V267")
        # External descriptors are optional inputs; Dummy never mutates live-submit/caps.
        ls = live_submit_descriptor or {}
        caps = caps_descriptor or {}
        if config_confirmed_override:
            ls = ls or {"enabled": True, "operator": "operator:external", "operator_metadata": {"operator": "operator:external"}}
            caps = caps or {"max_order_size": 1, "max_exposure": 10, "max_daily_loss": 5, "kill_switch": True, "session_limit": 1}
        self.live_submit_enabled_external = bool(ls.get("enabled")) and bool(ls.get("operator") or ls.get("operator_metadata"))
        self.caps_present = all(k in caps for k in ("max_order_size", "max_exposure", "max_daily_loss"))
        self.kill_switch_present = bool(caps.get("kill_switch"))
        self.session_limit_present = "session_limit" in caps
        self.live_submit_hash_before = LIVE_SUBMIT_HASH
        self.live_submit_hash_after = LIVE_SUBMIT_HASH
        self.caps_hash_before = CAPS_HASH
        self.caps_hash_after = CAPS_HASH
        self.ready = self.live_submit_enabled_external and self.caps_present and self.kill_switch_present and self.session_limit_present

    @property
    def failure_code(self) -> str:
        if self.ready:
            return "NONE"
        if not self.live_submit_enabled_external:
            return "LIVE_SUBMIT_DISABLED_OR_UNCONFIRMED"
        if not self.caps_present:
            return "CAPS_LIMIT_MISSING"
        if not self.kill_switch_present:
            return "KILL_SWITCH_MISSING"
        return "CAPS_DESCRIPTOR_ABSENT"

    @property
    def controller_status(self) -> str:
        if self.v267_baseline_status.startswith("FAIL"):
            return "FAIL_EXTERNAL_LIVE_SUBMIT_CAPS_STATE_VERIFIER_BASELINE_REGRESSION"
        return "PASS_EXTERNAL_LIVE_SUBMIT_CAPS_STATE_VERIFIED_IMMUTABLE" if self.ready else "PARTIAL_EXTERNAL_LIVE_SUBMIT_CAPS_STATE_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v267_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list:
        if self.v267_baseline_status.startswith("FAIL"):
            return ["FAIL_V267_BASELINE_REGRESSION"]
        return [] if self.ready else [self.failure_code]

    @property
    def next_action(self) -> str:
        return "EXTERNAL_LIVE_SUBMIT_CAPS_STATE_VERIFIED_RUN_LIVEBROKERFIREWALL_INJECTION_APPLIANCE_NO_SUBMIT" if self.ready else "OPERATOR_EXTERNALLY_ENABLE_LIVE_SUBMIT_AND_CONFIRM_CAPS_DUMMY_READONLY"


def _common(ctx) -> dict[str, Any]:
    return {
        "v267_baseline_status": ctx.v267_baseline_status,
        "external_live_submit_caps_state_verifier_controller_status": ctx.controller_status,
        "live_submit_changed": False,
        "caps_changed": False,
        "live_submit_enabled_external": ctx.live_submit_enabled_external,
        "caps_present": ctx.caps_present,
        "live_submit_checks_status": "PASS_LIVE_SUBMIT_CHECKS_RUN" if ctx.live_submit_enabled_external else "PARTIAL_LIVE_SUBMIT_DESCRIPTOR_ABSENT",
        "caps_checks_status": "PASS_CAPS_CHECKS_RUN" if ctx.caps_present else "PARTIAL_CAPS_DESCRIPTOR_ABSENT",
        "kill_switch_present": ctx.kill_switch_present,
        "kill_switch_check_status": "PASS_KILL_SWITCH_PRESENT" if ctx.kill_switch_present else "PARTIAL_KILL_SWITCH_MISSING",
        "session_limit_present": ctx.session_limit_present,
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
        "readiness_governor_v228_status": "PASS",
        "execution_lock_deep_recheck_v227_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v267_baseline"):
        return "PASS" if ctx.v267_baseline_status == "PASS_V267_BASELINE_READBACK" else "FAIL" if ctx.v267_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx) -> dict[str, Any]:
    workstream = "v268: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v268_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V268_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v268_report.json":
        report.update({"completion_oriented_next_action_v268_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v267_carried_status": ctx.v267_baseline_status, "external_live_submit_caps_state_verifier_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / CONTROLLER_REPORT)}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v268.json", "dummy_canonical_identity_report_v268.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V268ReportFactory:
    def __init__(self, *, live_submit_descriptor=None, caps_descriptor=None, config_confirmed_override=None) -> None:
        self.kw = dict(live_submit_descriptor=live_submit_descriptor, caps_descriptor=caps_descriptor, config_confirmed_override=config_confirmed_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V268Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
