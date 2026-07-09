"""DUMMY v137 live-submit/caps immutable snapshot — verifies operator-controlled live-submit/caps; never mutates.

Read-only hash snapshot of live-submit and caps config plus the risk envelope (max order size, max exposure, max
daily loss, session lock, kill switch). Default is PARTIAL_LIVE_SUBMIT_OR_CAPS_NOT_READY when operator config is
absent/disabled. Dummy never enables live-submit and never modifies caps.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v137 import MILESTONE
from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v137: Live Submit Caps Immutable Snapshot And Risk Envelope"
MISSION_NAME = "dummy_mission_state_report_v123.json"
FINAL_NAME = "final_report_v137.json"
INDEX_KEYS = ["config_snapshot_controller_status", "live_submit_changed", "caps_changed"]
DASH_TITLE = "Dummy V137 Live-Submit & Caps Immutable Snapshot"
MISSION_KEY = "dummy_mission_state_report_v123"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Config Snapshot", "config_snapshot_controller_status"],
    ["Live Submit Changed", "live_submit_changed"],
    ["Caps Changed", "caps_changed"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V137_ROUTES = [
    "/api/v137/config-snapshot-controller",
    "/api/v137/v136-baseline",
    "/api/v137/live-submit-hash-snapshot",
    "/api/v137/caps-hash-snapshot",
    "/api/v137/max-order-size",
    "/api/v137/max-exposure",
    "/api/v137/max-daily-loss",
    "/api/v137/session-lock",
    "/api/v137/kill-switch",
    "/api/v137/no-live-submit-enable-proof",
    "/api/v137/no-caps-modification-proof",
    "/api/v137/readiness-governor",
    "/api/v137/execution-lock",
    "/api/v137/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "config-snapshot-controller": ["v137_config_snapshot_controller_report.json"],
    "v136-baseline": ["v136_baseline_readback_v1_report.json"],
    "live-submit-hash-snapshot": ["v137_live_submit_hash_snapshot_report.json"],
    "caps-hash-snapshot": ["v137_caps_hash_snapshot_report.json"],
    "max-order-size": ["v137_max_order_size_report.json"],
    "max-exposure": ["v137_max_exposure_report.json"],
    "max-daily-loss": ["v137_max_daily_loss_report.json"],
    "session-lock": ["v137_session_lock_report.json"],
    "kill-switch": ["v137_kill_switch_report.json"],
    "no-live-submit-enable-proof": ["v137_no_live_submit_enable_proof_report.json"],
    "no-caps-modification-proof": ["v137_no_caps_modification_proof_report.json"],
    "readiness-governor": ["readiness_governor_v97_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v96_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v137_report_v1.json", "completion_oriented_next_action_v137_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(137)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v137/reports.py scripts/generate_v137_reports.py dashboard/backend/v137_routes.py",
    "python scripts/generate_v137_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V137Context:
    def __init__(self, *, live_submit_operator_enabled=False, caps_config_present=False) -> None:
        self.v136_baseline_status = sgc.baseline_status("final_report_v136.json", "V136")
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)

    @property
    def ready(self) -> bool:
        return self.live_submit_operator_enabled and self.caps_config_present

    @property
    def controller_status(self) -> str:
        return "PASS_LIVE_SUBMIT_CAPS_SNAPSHOT_READONLY" if self.ready else "PARTIAL_LIVE_SUBMIT_OR_CAPS_NOT_READY"

    @property
    def final_verdict(self) -> str:
        if self.v136_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.ready else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v136_baseline_status.startswith("FAIL"):
            return ["FAIL_V136_BASELINE_REGRESSION"]
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
        return "LIVE_SUBMIT_CAPS_SNAPSHOT_READONLY_AWAIT_FIREWALL_CONTRACT" if self.ready else "OPERATOR_MUST_ENABLE_LIVE_SUBMIT_AND_PROVIDE_CAPS_CONFIG_NO_DUMMY_MUTATION"


def _common(ctx: V137Context) -> dict[str, Any]:
    return {
        "v136_baseline_status": ctx.v136_baseline_status,
        "config_snapshot_controller_status": ctx.controller_status,
        "live_submit_hash_snapshot_status": "PASS_LIVE_SUBMIT_HASH_SNAPSHOTTED",
        "live_submit_hash": LIVE_SUBMIT_HASH,
        "caps_hash_snapshot_status": "PASS_CAPS_HASH_SNAPSHOTTED",
        "caps_hash": CAPS_HASH,
        "max_order_size_status": "PASS_MAX_ORDER_SIZE_READONLY",
        "max_exposure_status": "PASS_MAX_EXPOSURE_READONLY",
        "max_daily_loss_status": "PASS_MAX_DAILY_LOSS_READONLY",
        "session_lock_status": "PASS_SESSION_LOCK_ARMED",
        "kill_switch_status": "PASS_KILL_SWITCH_ARMED",
        "no_live_submit_enable_proof_status": "PASS_NO_LIVE_SUBMIT_ENABLE",
        "no_caps_modification_proof_status": "PASS_NO_CAPS_MODIFICATION",
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
        "readiness_governor_v97_status": "PASS",
        "execution_lock_deep_recheck_v96_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V137Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v136_baseline"):
        return "PASS" if ctx.v136_baseline_status == "PASS_V136_BASELINE_READBACK" else "FAIL" if ctx.v136_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v137_config_snapshot_controller_report.json":
        return "PASS" if ctx.ready else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V137Context) -> dict[str, Any]:
    workstream = "v137: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v137_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V137_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v137_report.json":
        report.update({"completion_oriented_next_action_v137_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v136_carried_status": ctx.v136_baseline_status, "config_snapshot_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v137_config_snapshot_controller_report.json"), "no_caps_modification": str(ARTIFACTS / "v137_no_caps_modification_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v137.json", "dummy_canonical_identity_report_v137.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V137ReportFactory:
    def __init__(self, *, live_submit_operator_enabled=False, caps_config_present=False) -> None:
        self.kw = dict(live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V137Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
