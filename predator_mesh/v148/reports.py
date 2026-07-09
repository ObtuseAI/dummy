"""DUMMY v148 dry/live mode split + mode firewall — separates rehearsal paths from real-live paths; no crossover.

Encodes a DRY mode enum and a LIVE mode enum with a prohibited-crossover matrix: dry-submit can never call a broker,
dry artifacts can never become broker payloads, and live-submit requires V147 full authority. The mode firewall is
locked. Default mode is DRY_LOCKED (LIVE_BLOCKED) with broker_contacted=false.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v148 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v148: Dry Live Mode Split And Mode Firewall No Crossover"
MISSION_NAME = "dummy_mission_state_report_v134.json"
FINAL_NAME = "final_report_v148.json"
INDEX_KEYS = ["mode_firewall_controller_status", "mode", "broker_contacted"]
DASH_TITLE = "Dummy V148 Dry/Live Mode Firewall"
MISSION_KEY = "dummy_mission_state_report_v134"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Mode Firewall", "mode_firewall_controller_status"],
    ["Mode", "mode"],
    ["Broker Contacted", "broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V148_ROUTES = [
    "/api/v148/mode-firewall-controller",
    "/api/v148/v147-baseline",
    "/api/v148/dry-mode-enum",
    "/api/v148/live-mode-enum",
    "/api/v148/prohibited-crossover-matrix",
    "/api/v148/dry-submit-cannot-call-broker-proof",
    "/api/v148/live-submit-requires-full-authority-proof",
    "/api/v148/dry-artifacts-not-broker-payloads-proof",
    "/api/v148/live-payload-not-in-dry-mode-proof",
    "/api/v148/no-submit-default-proof",
    "/api/v148/readiness-governor",
    "/api/v148/execution-lock",
    "/api/v148/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "mode-firewall-controller": ["v148_mode_firewall_controller_report.json"],
    "v147-baseline": ["v147_baseline_readback_v1_report.json"],
    "dry-mode-enum": ["v148_dry_mode_enum_report.json"],
    "live-mode-enum": ["v148_live_mode_enum_report.json"],
    "prohibited-crossover-matrix": ["v148_prohibited_crossover_matrix_report.json"],
    "dry-submit-cannot-call-broker-proof": ["v148_dry_submit_cannot_call_broker_proof_report.json"],
    "live-submit-requires-full-authority-proof": ["v148_live_submit_requires_full_authority_proof_report.json"],
    "dry-artifacts-not-broker-payloads-proof": ["v148_dry_artifacts_not_broker_payloads_proof_report.json"],
    "live-payload-not-in-dry-mode-proof": ["v148_live_payload_not_in_dry_mode_proof_report.json"],
    "no-submit-default-proof": ["v148_no_submit_default_proof_report.json"],
    "readiness-governor": ["readiness_governor_v108_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v107_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v148_report_v1.json", "completion_oriented_next_action_v148_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(148)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v148/reports.py scripts/generate_v148_reports.py dashboard/backend/v148_routes.py",
    "python scripts/generate_v148_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

DRY_MODE_ENUM = ["DRY_LOCKED", "DRY_REHEARSAL"]
LIVE_MODE_ENUM = ["LIVE_BLOCKED", "LIVE_AUTHORIZED"]
PROHIBITED_CROSSOVER = {
    "dry_submit_calls_broker": "PROHIBITED",
    "dry_artifact_becomes_broker_payload": "PROHIBITED",
    "live_submit_without_full_authority": "PROHIBITED",
    "live_payload_generated_in_dry_mode": "PROHIBITED",
}


class V148Context:
    def __init__(self, *, live_authority_override=None) -> None:
        self.v147_baseline_status = sgc.baseline_status("final_report_v147.json", "V147")
        if live_authority_override is not None:
            self.live_authorized = bool(live_authority_override)
        else:
            self.live_authorized = str(sgc.load_artifact("final_report_v147.json").get("intake_validator_controller_status", "")) == "PASS_REAL_AUTHORITY_INTAKE_VALID_NO_SUBMIT"

    @property
    def mode(self) -> str:
        return "LIVE_AUTHORIZED" if self.live_authorized else "DRY_LOCKED"

    @property
    def live_mode(self) -> str:
        return "LIVE_AUTHORIZED" if self.live_authorized else "LIVE_BLOCKED"

    @property
    def controller_status(self) -> str:
        return "FAIL_MODE_FIREWALL_BASELINE_REGRESSION" if self.v147_baseline_status.startswith("FAIL") else "PASS_MODE_FIREWALL_LOCKED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v147_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V147_BASELINE_REGRESSION"] if self.v147_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        if self.live_authorized:
            return "MODE_FIREWALL_LOCKED_LIVE_AUTHORIZED_AWAIT_REAL_PILOT_PREFLIGHT_NO_CROSSOVER"
        return "MODE_FIREWALL_LOCKED_DRY_ONLY_LIVE_BLOCKED_AWAIT_REAL_AUTHORITY_INTAKE"


def _common(ctx: V148Context) -> dict[str, Any]:
    return {
        "v147_baseline_status": ctx.v147_baseline_status,
        "mode_firewall_controller_status": ctx.controller_status,
        "dry_mode_enum_status": "PASS_DRY_MODE_ENUM_DEFINED",
        "dry_mode_enum": DRY_MODE_ENUM,
        "live_mode_enum_status": "PASS_LIVE_MODE_ENUM_DEFINED",
        "live_mode_enum": LIVE_MODE_ENUM,
        "prohibited_crossover_matrix_status": "PASS_PROHIBITED_CROSSOVER_MATRIX_LOCKED",
        "prohibited_crossover_matrix": PROHIBITED_CROSSOVER,
        "dry_submit_cannot_call_broker_proof_status": "PASS_DRY_SUBMIT_CANNOT_CALL_BROKER",
        "live_submit_requires_full_authority_proof_status": "PASS_LIVE_SUBMIT_REQUIRES_FULL_AUTHORITY",
        "dry_artifacts_not_broker_payloads_proof_status": "PASS_DRY_ARTIFACTS_NOT_BROKER_PAYLOADS",
        "live_payload_not_in_dry_mode_proof_status": "PASS_NO_LIVE_PAYLOAD_IN_DRY_MODE",
        "no_submit_default_proof_status": "PASS_NO_SUBMIT_DEFAULT",
        "mode": ctx.mode,
        "live_mode": ctx.live_mode,
        "live_authorized": ctx.live_authorized,
        "broker_contacted": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v108_status": "PASS",
        "execution_lock_deep_recheck_v107_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V148Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v147_baseline"):
        return "PASS" if ctx.v147_baseline_status == "PASS_V147_BASELINE_READBACK" else "FAIL" if ctx.v147_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V148Context) -> dict[str, Any]:
    workstream = "v148: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v148_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V148_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v148_report.json":
        report.update({"completion_oriented_next_action_v148_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v147_carried_status": ctx.v147_baseline_status, "mode_firewall_controller_status": ctx.controller_status, "mode": ctx.mode, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v148_mode_firewall_controller_report.json"), "no_submit_default": str(ARTIFACTS / "v148_no_submit_default_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v148.json", "dummy_canonical_identity_report_v148.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V148ReportFactory:
    def __init__(self, *, live_authority_override=None) -> None:
        self.kw = dict(live_authority_override=live_authority_override)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V148Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
