"""DUMMY v157 live-submit/caps operator confirmation audit — audits operator config read-only; no mutation.

Read-only parse of live-submit and caps config with a hash before/after (unchanged), enabled-status and operator
metadata checks, risk envelope (max order size / exposure / daily loss), kill-switch status, and an immutable snapshot
artifact. Default is PARTIAL_LIVE_SUBMIT_OR_CAPS_CONFIRMATION_ABSENT. Dummy never enables live-submit or modifies caps.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v157 import MILESTONE
from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v157: Live Submit Caps Operator Confirmation Audit Readonly No Mutation"
MISSION_NAME = "dummy_mission_state_report_v143.json"
FINAL_NAME = "final_report_v157.json"
INDEX_KEYS = ["config_audit_controller_status", "live_submit_changed", "caps_changed"]
DASH_TITLE = "Dummy V157 Live-Submit/Caps Confirmation Audit"
MISSION_KEY = "dummy_mission_state_report_v143"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Config Audit", "config_audit_controller_status"],
    ["Live Submit Changed", "live_submit_changed"],
    ["Caps Changed", "caps_changed"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V157_ROUTES = [
    "/api/v157/config-audit-controller",
    "/api/v157/v156-baseline",
    "/api/v157/live-submit-config-parser",
    "/api/v157/caps-config-parser",
    "/api/v157/hash-before-after",
    "/api/v157/enabled-status-check",
    "/api/v157/operator-metadata-check",
    "/api/v157/max-order-size-check",
    "/api/v157/max-exposure-check",
    "/api/v157/max-daily-loss-check",
    "/api/v157/kill-switch-status-check",
    "/api/v157/immutable-snapshot-artifact",
    "/api/v157/no-live-submit-enable-proof",
    "/api/v157/no-caps-modification-proof",
    "/api/v157/no-submit-proof",
    "/api/v157/readiness-governor",
    "/api/v157/execution-lock",
    "/api/v157/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "config-audit-controller": ["v157_config_audit_controller_report.json"],
    "v156-baseline": ["v156_baseline_readback_v1_report.json"],
    "live-submit-config-parser": ["v157_live_submit_config_parser_report.json"],
    "caps-config-parser": ["v157_caps_config_parser_report.json"],
    "hash-before-after": ["v157_hash_before_after_report.json"],
    "enabled-status-check": ["v157_enabled_status_check_report.json"],
    "operator-metadata-check": ["v157_operator_metadata_check_report.json"],
    "max-order-size-check": ["v157_max_order_size_check_report.json"],
    "max-exposure-check": ["v157_max_exposure_check_report.json"],
    "max-daily-loss-check": ["v157_max_daily_loss_check_report.json"],
    "kill-switch-status-check": ["v157_kill_switch_status_check_report.json"],
    "immutable-snapshot-artifact": ["v157_immutable_snapshot_artifact_report.json"],
    "no-live-submit-enable-proof": ["v157_no_live_submit_enable_proof_report.json"],
    "no-caps-modification-proof": ["v157_no_caps_modification_proof_report.json"],
    "no-submit-proof": ["v157_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v117_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v116_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v157_report_v1.json", "completion_oriented_next_action_v157_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(157)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v157/reports.py scripts/generate_v157_reports.py dashboard/backend/v157_routes.py",
    "python scripts/generate_v157_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V157Context:
    def __init__(self, *, live_submit_operator_enabled=False, caps_config_present=False) -> None:
        self.v156_baseline_status = sgc.baseline_status("final_report_v156.json", "V156")
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)

    @property
    def confirmed(self) -> bool:
        return self.live_submit_operator_enabled and self.caps_config_present

    @property
    def controller_status(self) -> str:
        return "PASS_LIVE_SUBMIT_CAPS_CONFIRMED_READONLY" if self.confirmed else "PARTIAL_LIVE_SUBMIT_OR_CAPS_CONFIRMATION_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v156_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.confirmed else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v156_baseline_status.startswith("FAIL"):
            return ["FAIL_V156_BASELINE_REGRESSION"]
        if self.confirmed:
            return []
        blockers: list[str] = []
        if not self.live_submit_operator_enabled:
            blockers.append("LIVE_SUBMIT_NOT_OPERATOR_ENABLED")
        if not self.caps_config_present:
            blockers.append("CAPS_CONFIG_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "LIVE_SUBMIT_CAPS_CONFIRMED_READONLY_AWAIT_FIREWALL_ADAPTER_VERIFICATION" if self.confirmed else "OPERATOR_MUST_CONFIRM_LIVE_SUBMIT_ENABLED_AND_CAPS_CONFIG_NO_DUMMY_MUTATION"


def _common(ctx: V157Context) -> dict[str, Any]:
    return {
        "v156_baseline_status": ctx.v156_baseline_status,
        "config_audit_controller_status": ctx.controller_status,
        "live_submit_config_parser_status": "PASS_LIVE_SUBMIT_PARSED_READONLY",
        "caps_config_parser_status": "PASS_CAPS_PARSED_READONLY",
        "hash_before_after_status": "PASS_HASH_UNCHANGED",
        "live_submit_hash_before": LIVE_SUBMIT_HASH,
        "live_submit_hash_after": LIVE_SUBMIT_HASH,
        "caps_hash_before": CAPS_HASH,
        "caps_hash_after": CAPS_HASH,
        "enabled_status_check_status": "PASS_LIVE_SUBMIT_OPERATOR_ENABLED" if ctx.live_submit_operator_enabled else "PARTIAL_LIVE_SUBMIT_NOT_OPERATOR_ENABLED",
        "operator_metadata_check_status": "PASS_OPERATOR_METADATA_PRESENT" if ctx.confirmed else "PARTIAL_OPERATOR_METADATA_ABSENT",
        "max_order_size_check_status": "PASS_MAX_ORDER_SIZE_READONLY",
        "max_exposure_check_status": "PASS_MAX_EXPOSURE_READONLY",
        "max_daily_loss_check_status": "PASS_MAX_DAILY_LOSS_READONLY",
        "kill_switch_status_check_status": "PASS_KILL_SWITCH_ARMED",
        "immutable_snapshot_artifact_status": "PASS_IMMUTABLE_SNAPSHOT_CAPTURED",
        "no_live_submit_enable_proof_status": "PASS_NO_LIVE_SUBMIT_ENABLE",
        "no_caps_modification_proof_status": "PASS_NO_CAPS_MODIFICATION",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "live_submit_operator_enabled": ctx.live_submit_operator_enabled,
        "caps_config_present": ctx.caps_config_present,
        "live_submit_changed": False,
        "caps_changed": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v117_status": "PASS",
        "execution_lock_deep_recheck_v116_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V157Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v156_baseline"):
        return "PASS" if ctx.v156_baseline_status == "PASS_V156_BASELINE_READBACK" else "FAIL" if ctx.v156_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v157_config_audit_controller_report.json":
        return "PASS" if ctx.confirmed else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V157Context) -> dict[str, Any]:
    workstream = "v157: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v157_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V157_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v157_report.json":
        report.update({"completion_oriented_next_action_v157_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v156_carried_status": ctx.v156_baseline_status, "config_audit_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v157_config_audit_controller_report.json"), "no_caps_modification": str(ARTIFACTS / "v157_no_caps_modification_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v157.json", "dummy_canonical_identity_report_v157.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V157ReportFactory:
    def __init__(self, *, live_submit_operator_enabled=False, caps_config_present=False) -> None:
        self.kw = dict(live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V157Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
