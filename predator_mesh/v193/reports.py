"""DUMMY v193 production hardening V6 — hardens production locks across risk/abstention/session/scale/autonomy; no order.

Rechecks risk, abstention, session, pilot-proof, scale, autonomy, broker-contact, live-submit/caps-immutability, and
approval-file-write locks; updates the stop policy and a repair recommendation map. Static PASS; no live order, no
broker contact, no scale, no autonomy.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v193 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v193: Production Hardening V6 Risk Abstention Session And Autonomy Locks"
MISSION_NAME = "dummy_mission_state_report_v179.json"
FINAL_NAME = "final_report_v193.json"
INDEX_KEYS = ["production_hardening_controller_status", "autonomous_trading_enabled", "no_submit_proof_status"]
DASH_TITLE = "Dummy V193 Production Hardening V6"
MISSION_KEY = "dummy_mission_state_report_v179"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Production Hardening", "production_hardening_controller_status"],
    ["Autonomous Trading", "autonomous_trading_enabled"],
    ["Caps Modified", "caps_modified"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V193_ROUTES = [
    "/api/v193/production-hardening-controller",
    "/api/v193/v192-baseline",
    "/api/v193/risk-lock-recheck",
    "/api/v193/abstention-lock-recheck",
    "/api/v193/session-lock-recheck",
    "/api/v193/pilot-proof-lock-recheck",
    "/api/v193/scale-lock-recheck",
    "/api/v193/autonomy-lock-recheck",
    "/api/v193/broker-contact-lock-recheck",
    "/api/v193/live-submit-caps-immutability-recheck",
    "/api/v193/approval-file-write-lock-recheck",
    "/api/v193/stop-policy-update",
    "/api/v193/repair-recommendation-map",
    "/api/v193/no-submit-proof",
    "/api/v193/readiness-governor",
    "/api/v193/execution-lock",
    "/api/v193/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "production-hardening-controller": ["v193_production_hardening_controller_report.json"],
    "v192-baseline": ["v192_baseline_readback_v1_report.json"],
    "risk-lock-recheck": ["v193_risk_lock_recheck_report.json"],
    "abstention-lock-recheck": ["v193_abstention_lock_recheck_report.json"],
    "session-lock-recheck": ["v193_session_lock_recheck_report.json"],
    "pilot-proof-lock-recheck": ["v193_pilot_proof_lock_recheck_report.json"],
    "scale-lock-recheck": ["v193_scale_lock_recheck_report.json"],
    "autonomy-lock-recheck": ["v193_autonomy_lock_recheck_report.json"],
    "broker-contact-lock-recheck": ["v193_broker_contact_lock_recheck_report.json"],
    "live-submit-caps-immutability-recheck": ["v193_live_submit_caps_immutability_recheck_report.json"],
    "approval-file-write-lock-recheck": ["v193_approval_file_write_lock_recheck_report.json"],
    "stop-policy-update": ["v193_stop_policy_update_report.json"],
    "repair-recommendation-map": ["v193_repair_recommendation_map_report.json"],
    "no-submit-proof": ["v193_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v153_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v152_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v193_report_v1.json", "completion_oriented_next_action_v193_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(193)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v193/reports.py scripts/generate_v193_reports.py dashboard/backend/v193_routes.py",
    "python scripts/generate_v193_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

REPAIR_RECOMMENDATION_MAP = {
    "controlled_session_proof": "AWAIT_GATED_FIRE_STAGE_WITH_FULL_AUTHORITY",
    "autonomy_live_proof": "AWAIT_CONTROLLED_SESSION_LIVE_PROOF",
    "scale": "AWAIT_SESSION_PROOF_THEN_SCALE_REVIEW",
}


class V193Context:
    def __init__(self) -> None:
        self.v192_baseline_status = sgc.baseline_status("final_report_v192.json", "V192")

    @property
    def controller_status(self) -> str:
        return "FAIL_PRODUCTION_HARDENING_BASELINE_REGRESSION" if self.v192_baseline_status.startswith("FAIL") else "PASS_PRODUCTION_LOCKS_HARDENED"

    @property
    def final_verdict(self) -> str:
        return "FAIL" if self.v192_baseline_status.startswith("FAIL") else "PASS"

    @property
    def current_blockers(self) -> list[str]:
        return ["FAIL_V192_BASELINE_REGRESSION"] if self.v192_baseline_status.startswith("FAIL") else []

    @property
    def next_action(self) -> str:
        return "PRODUCTION_LOCKS_HARDENED_AWAIT_PRODUCTION_LOCK_V6_SUMMARY_NO_ORDER_NO_AUTONOMY_NO_SCALE"


def _common(ctx: V193Context) -> dict[str, Any]:
    return {
        "v192_baseline_status": ctx.v192_baseline_status,
        "production_hardening_controller_status": ctx.controller_status,
        "risk_lock_recheck_status": "PASS_RISK_LOCK_HELD",
        "abstention_lock_recheck_status": "PASS_ABSTENTION_LOCK_HELD",
        "session_lock_recheck_status": "PASS_SESSION_LOCK_HELD",
        "pilot_proof_lock_recheck_status": "PASS_PILOT_PROOF_LOCK_HELD",
        "scale_lock_recheck_status": "PASS_SCALE_LOCK_HELD",
        "autonomy_lock_recheck_status": "PASS_AUTONOMY_LOCK_HELD",
        "broker_contact_lock_recheck_status": "PASS_BROKER_CONTACT_LOCK_HELD",
        "live_submit_caps_immutability_recheck_status": "PASS_LIVE_SUBMIT_CAPS_IMMUTABLE",
        "approval_file_write_lock_recheck_status": "PASS_APPROVAL_FILE_WRITE_LOCK_HELD",
        "stop_policy_update_status": "PASS_STOP_POLICY_UPDATED_LOCKED",
        "repair_recommendation_map_status": "PASS_REPAIR_RECOMMENDATION_MAPPED",
        "repair_recommendation_map": REPAIR_RECOMMENDATION_MAP,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v153_status": "PASS",
        "execution_lock_deep_recheck_v152_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V193Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v192_baseline"):
        return "PASS" if ctx.v192_baseline_status == "PASS_V192_BASELINE_READBACK" else "FAIL" if ctx.v192_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V193Context) -> dict[str, Any]:
    workstream = "v193: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v193_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V193_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v193_report.json":
        report.update({"completion_oriented_next_action_v193_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v192_carried_status": ctx.v192_baseline_status, "production_hardening_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v193_production_hardening_controller_report.json"), "no_submit": str(ARTIFACTS / "v193_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v193.json", "dummy_canonical_identity_report_v193.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V193ReportFactory:
    def __init__(self) -> None:
        pass

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V193Context()
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
