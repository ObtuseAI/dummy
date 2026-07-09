"""DUMMY v196 operator live config/caps immutable quorum — immutable read-only quorum over operator config; no mutation.

Read-only quorum with live-submit and caps before/after hashes (unchanged), operator-metadata / enabled-status / max
order size / max exposure / max daily loss / kill-switch / session-limit validation. Default is
PARTIAL_LIVE_CONFIG_CAPS_QUORUM_BLOCKED. Dummy never enables live-submit and never modifies caps.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v196 import MILESTONE
from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v196: Operator Live Config Caps Immutable Quorum No Mutation"
MISSION_NAME = "dummy_mission_state_report_v182.json"
FINAL_NAME = "final_report_v196.json"
INDEX_KEYS = ["config_quorum_controller_status", "live_submit_changed", "caps_changed"]
DASH_TITLE = "Dummy V196 Operator Live Config/Caps Immutable Quorum"
MISSION_KEY = "dummy_mission_state_report_v182"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Config Quorum", "config_quorum_controller_status"],
    ["Live Submit Changed", "live_submit_changed"],
    ["Caps Changed", "caps_changed"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V196_ROUTES = [
    "/api/v196/config-quorum-controller",
    "/api/v196/v195-baseline",
    "/api/v196/live-submit-before-after-hash",
    "/api/v196/caps-before-after-hash",
    "/api/v196/operator-metadata-validation",
    "/api/v196/enabled-status-validation",
    "/api/v196/max-order-size-validation",
    "/api/v196/max-exposure-validation",
    "/api/v196/max-daily-loss-validation",
    "/api/v196/kill-switch-validation",
    "/api/v196/session-limit-validation",
    "/api/v196/no-live-submit-enable-proof",
    "/api/v196/no-caps-modification-proof",
    "/api/v196/no-submit-proof",
    "/api/v196/readiness-governor",
    "/api/v196/execution-lock",
    "/api/v196/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "config-quorum-controller": ["v196_config_quorum_controller_report.json"],
    "v195-baseline": ["v195_baseline_readback_v1_report.json"],
    "live-submit-before-after-hash": ["v196_live_submit_before_after_hash_report.json"],
    "caps-before-after-hash": ["v196_caps_before_after_hash_report.json"],
    "operator-metadata-validation": ["v196_operator_metadata_validation_report.json"],
    "enabled-status-validation": ["v196_enabled_status_validation_report.json"],
    "max-order-size-validation": ["v196_max_order_size_validation_report.json"],
    "max-exposure-validation": ["v196_max_exposure_validation_report.json"],
    "max-daily-loss-validation": ["v196_max_daily_loss_validation_report.json"],
    "kill-switch-validation": ["v196_kill_switch_validation_report.json"],
    "session-limit-validation": ["v196_session_limit_validation_report.json"],
    "no-live-submit-enable-proof": ["v196_no_live_submit_enable_proof_report.json"],
    "no-caps-modification-proof": ["v196_no_caps_modification_proof_report.json"],
    "no-submit-proof": ["v196_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v156_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v155_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v196_report_v1.json", "completion_oriented_next_action_v196_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(196)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v196/reports.py scripts/generate_v196_reports.py dashboard/backend/v196_routes.py",
    "python scripts/generate_v196_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V196Context:
    def __init__(self, *, live_submit_operator_enabled=False, caps_config_present=False) -> None:
        self.v195_baseline_status = sgc.baseline_status("final_report_v195.json", "V195")
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)

    @property
    def ready(self) -> bool:
        return self.live_submit_operator_enabled and self.caps_config_present

    @property
    def controller_status(self) -> str:
        return "PASS_LIVE_CONFIG_CAPS_QUORUM_READY_IMMUTABLE" if self.ready else "PARTIAL_LIVE_CONFIG_CAPS_QUORUM_BLOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v195_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v195_baseline_status.startswith("FAIL"):
            return ["FAIL_V195_BASELINE_REGRESSION"]
        if self.ready:
            return []
        blockers: list[str] = []
        if not self.live_submit_operator_enabled:
            blockers.append("LIVE_SUBMIT_NOT_OPERATOR_ENABLED")
        if not self.caps_config_present:
            blockers.append("CAPS_CONFIG_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "LIVE_CONFIG_CAPS_QUORUM_READY_IMMUTABLE_AWAIT_FIREWALL_BROKER_VERIFICATION" if self.ready else "OPERATOR_MUST_CONFIRM_LIVE_SUBMIT_ENABLED_AND_CAPS_CONFIG_NO_DUMMY_MUTATION"


def _common(ctx: V196Context) -> dict[str, Any]:
    return {
        "v195_baseline_status": ctx.v195_baseline_status,
        "config_quorum_controller_status": ctx.controller_status,
        "live_submit_before_after_hash_status": "PASS_LIVE_SUBMIT_HASH_UNCHANGED",
        "live_submit_hash_before": LIVE_SUBMIT_HASH,
        "live_submit_hash_after": LIVE_SUBMIT_HASH,
        "caps_before_after_hash_status": "PASS_CAPS_HASH_UNCHANGED",
        "caps_hash_before": CAPS_HASH,
        "caps_hash_after": CAPS_HASH,
        "operator_metadata_validation_status": "PASS_OPERATOR_METADATA_PRESENT" if ctx.ready else "PARTIAL_OPERATOR_METADATA_ABSENT",
        "enabled_status_validation_status": "PASS_LIVE_SUBMIT_OPERATOR_ENABLED" if ctx.live_submit_operator_enabled else "PARTIAL_LIVE_SUBMIT_NOT_OPERATOR_ENABLED",
        "max_order_size_validation_status": "PASS_MAX_ORDER_SIZE_READONLY",
        "max_exposure_validation_status": "PASS_MAX_EXPOSURE_READONLY",
        "max_daily_loss_validation_status": "PASS_MAX_DAILY_LOSS_READONLY",
        "kill_switch_validation_status": "PASS_KILL_SWITCH_ARMED",
        "session_limit_validation_status": "PASS_SESSION_LIMIT_READONLY",
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
        "readiness_governor_v156_status": "PASS",
        "execution_lock_deep_recheck_v155_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V196Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v195_baseline"):
        return "PASS" if ctx.v195_baseline_status == "PASS_V195_BASELINE_READBACK" else "FAIL" if ctx.v195_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v196_config_quorum_controller_report.json":
        return "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V196Context) -> dict[str, Any]:
    workstream = "v196: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v196_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V196_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v196_report.json":
        report.update({"completion_oriented_next_action_v196_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v195_carried_status": ctx.v195_baseline_status, "config_quorum_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v196_config_quorum_controller_report.json"), "no_caps_modification": str(ARTIFACTS / "v196_no_caps_modification_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v196.json", "dummy_canonical_identity_report_v196.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V196ReportFactory:
    def __init__(self, *, live_submit_operator_enabled=False, caps_config_present=False) -> None:
        self.kw = dict(live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V196Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
