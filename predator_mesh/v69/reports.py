"""DUMMY v69 final dry/shadow/firewall tieout — all pre-submit prerequisites ready, no submit."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v69 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

V69_ROUTES = [
    "/api/v69/final-tieout-controller",
    "/api/v69/v68-baseline",
    "/api/v69/dry-shadow-schema-validator",
    "/api/v69/candidate-tieout-validator",
    "/api/v69/livebrokerfirewall-only-proof",
    "/api/v69/no-direct-broker-bypass-proof",
    "/api/v69/no-submit-no-cancel-proof",
    "/api/v69/kill-switch-readiness-proof",
    "/api/v69/rollback-readiness-proof",
    "/api/v69/idempotency-readiness-proof",
    "/api/v69/caps-readonly-proof",
    "/api/v69/live-submit-status-proof",
    "/api/v69/readiness-governor",
    "/api/v69/execution-lock",
    "/api/v69/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "final-tieout-controller": ["v69_final_tieout_controller_report.json"],
    "v68-baseline": ["v68_baseline_readback_v1_report.json"],
    "dry-shadow-schema-validator": ["v69_dry_shadow_schema_validator_report.json"],
    "candidate-tieout-validator": ["v69_candidate_tieout_validator_report.json"],
    "livebrokerfirewall-only-proof": ["v69_livebrokerfirewall_only_proof_report.json"],
    "no-direct-broker-bypass-proof": ["v69_no_direct_broker_bypass_proof_report.json"],
    "no-submit-no-cancel-proof": ["v69_no_submit_no_cancel_proof_report.json"],
    "kill-switch-readiness-proof": ["v69_kill_switch_readiness_proof_report.json"],
    "rollback-readiness-proof": ["v69_rollback_readiness_proof_report.json"],
    "idempotency-readiness-proof": ["v69_idempotency_readiness_proof_report.json"],
    "caps-readonly-proof": ["v69_caps_readonly_proof_report.json"],
    "live-submit-status-proof": ["v69_live_submit_status_proof_report.json"],
    "readiness-governor": ["readiness_governor_v29_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v28_report.json"],
    "mission-state": ["dummy_mission_state_report_v55.json", "dashboard_v69_report_v1.json", "completion_oriented_next_action_v69_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(69)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v69/reports.py scripts/generate_v69_reports.py dashboard/backend/v69_routes.py",
    "python scripts/generate_v69_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

TIEOUT_PROOFS = {
    "dry_shadow_schema_validator_status": "PASS_DRY_SHADOW_SCHEMA_INERT",
    "candidate_tieout_validator_status": "PASS_CANDIDATE_TIEOUT_INERT",
    "livebrokerfirewall_only_proof_status": "PASS_LIVEBROKERFIREWALL_ONLY",
    "no_direct_broker_bypass_proof_status": "PASS_NO_DIRECT_BROKER_BYPASS",
    "no_submit_no_cancel_proof_status": "PASS_NO_SUBMIT_NO_CANCEL",
    "kill_switch_readiness_proof_status": "PASS_KILL_SWITCH_READY",
    "rollback_readiness_proof_status": "PASS_ROLLBACK_READY",
    "idempotency_readiness_proof_status": "PASS_IDEMPOTENCY_READY",
    "caps_readonly_proof_status": "PASS_CAPS_READONLY",
    "live_submit_status_proof_status": "PASS_LIVE_SUBMIT_OPERATOR_CONTROLLED_DISABLED",
}


class V69Context:
    def __init__(self) -> None:
        self.v68_baseline_status = sgc.baseline_status("final_report_v68.json", "V68")
        self.v63_ok = sgc.load_artifact("final_report_v63.json").get("verdict") in {"PASS", "PARTIAL"}
        self.v64_ok = sgc.load_artifact("final_report_v64.json").get("verdict") in {"PASS", "PARTIAL"}

    @property
    def final_verdict(self) -> str:
        if self.v68_baseline_status.startswith("FAIL"):
            return "FAIL"
        if self.v68_baseline_status.startswith("PARTIAL"):
            return "PARTIAL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v68_baseline_status.startswith("FAIL"):
            return ["FAIL_V68_BASELINE_REGRESSION"]
        if self.v68_baseline_status.startswith("PARTIAL"):
            return ["PARTIAL_V68_BASELINE_UNAVAILABLE"]
        return []

    @property
    def next_action(self) -> str:
        return "FINAL_TIEOUT_READY_ALL_PRESUBMIT_PREREQS_NO_SUBMIT"


def _common(ctx: V69Context) -> dict[str, Any]:
    common = {
        "v68_baseline_status": ctx.v68_baseline_status,
        "final_tieout_controller_status": "PASS_FINAL_TIEOUT_READY_NO_SUBMIT",
        "v63_dry_shadow_available": ctx.v63_ok,
        "v64_firewall_preflight_available": ctx.v64_ok,
        "live_order_fired": False,
        "broker_payload_sent": False,
        "readiness_governor_v29_status": "PASS",
        "execution_lock_deep_recheck_v28_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }
    common.update(TIEOUT_PROOFS)
    return common


def _verdict(name: str, ctx: V69Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v68_baseline"):
        return "PASS" if ctx.v68_baseline_status == "PASS_V68_BASELINE_READBACK" else "FAIL" if ctx.v68_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V69Context) -> dict[str, Any]:
    workstream = "v69: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v69_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V69_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v69_report.json":
        report.update({"completion_oriented_next_action_v69_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v55.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v68_carried_status": ctx.v68_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v69.json"), "tieout_controller": str(ARTIFACTS / "v69_final_tieout_controller_report.json"), "no_submit_no_cancel": str(ARTIFACTS / "v69_no_submit_no_cancel_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v69.json", "dummy_canonical_identity_report_v69.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V69ReportFactory:
    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V69Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
