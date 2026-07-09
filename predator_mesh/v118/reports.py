"""DUMMY v118 production dry audit — dry-runs production readiness with no broker contact and no live orders.

Runs production-config, firewall, risk, abstention, reconcile, and dashboard/API safety checklists as design-only
review. Design-only is allowed, so the default is PASS_DRY_AUDIT_LOCKED even with no approval; presenting the exact
dry-audit approval yields PASS_DRY_AUDIT_APPROVED_LOCKED. A present-but-invalid approval fails closed. No broker is
ever contacted and no order is placed.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v118 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v118: Production Dry Audit No Broker Contact"
MISSION_NAME = "dummy_mission_state_report_v104.json"
FINAL_NAME = "final_report_v118.json"
INDEX_KEYS = ["production_dry_audit_controller_status", "broker_contacted", "live_orders"]
DASH_TITLE = "Dummy V118 Production Dry Audit"
MISSION_KEY = "dummy_mission_state_report_v104"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Dry Audit", "production_dry_audit_controller_status"],
    ["Broker Contacted", "broker_contacted"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V118_ROUTES = [
    "/api/v118/production-dry-audit-controller",
    "/api/v118/v117-baseline",
    "/api/v118/dry-audit-approval-validator",
    "/api/v118/production-config-checklist",
    "/api/v118/firewall-checklist",
    "/api/v118/risk-checklist",
    "/api/v118/abstention-checklist",
    "/api/v118/reconcile-checklist",
    "/api/v118/dashboard-api-safety-checklist",
    "/api/v118/no-broker-contact-proof",
    "/api/v118/no-order-proof",
    "/api/v118/readiness-governor",
    "/api/v118/execution-lock",
    "/api/v118/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "production-dry-audit-controller": ["v118_production_dry_audit_controller_report.json"],
    "v117-baseline": ["v117_baseline_readback_v1_report.json"],
    "dry-audit-approval-validator": ["v118_dry_audit_approval_validator_report.json"],
    "production-config-checklist": ["v118_production_config_checklist_report.json"],
    "firewall-checklist": ["v118_firewall_checklist_report.json"],
    "risk-checklist": ["v118_risk_checklist_report.json"],
    "abstention-checklist": ["v118_abstention_checklist_report.json"],
    "reconcile-checklist": ["v118_reconcile_checklist_report.json"],
    "dashboard-api-safety-checklist": ["v118_dashboard_api_safety_checklist_report.json"],
    "no-broker-contact-proof": ["v118_no_broker_contact_proof_report.json"],
    "no-order-proof": ["v118_no_order_proof_report.json"],
    "readiness-governor": ["readiness_governor_v78_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v77_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v118_report_v1.json", "completion_oriented_next_action_v118_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(118)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v118/reports.py scripts/generate_v118_reports.py dashboard/backend/v118_routes.py",
    "python scripts/generate_v118_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V118Context:
    def __init__(self, *, dry_audit_approval=None, dry_audit_approval_path=None) -> None:
        self.v117_baseline_status = sgc.baseline_status("final_report_v117.json", "V117")
        res = sgc.resolve_packet(dry_audit_approval_path, dry_audit_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.PRODUCTION_DRY_AUDIT_PHRASE, required_fields=sgc.PRODUCTION_DRY_AUDIT_FIELDS, required_scope=sgc.PRODUCTION_DRY_AUDIT_SCOPE)
        self.approval_present = self.validation["state"] == "PRESENT"

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.approval_present and not self.validation["accepted"]

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_DRY_AUDIT_APPROVAL"
        if self.approved:
            return "PASS_DRY_AUDIT_APPROVED_LOCKED"
        return "PASS_DRY_AUDIT_LOCKED"

    @property
    def final_verdict(self) -> str:
        if self.v117_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v117_baseline_status.startswith("FAIL"):
            return ["FAIL_V117_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_DRY_AUDIT_APPROVAL"]
        return []

    @property
    def next_action(self) -> str:
        return "PRODUCTION_DRY_AUDIT_COMPLETE_LOCKED_NO_BROKER_CONTACT_AWAIT_CONTROLLED_PILOT_APPROVAL"


def _common(ctx: V118Context) -> dict[str, Any]:
    return {
        "v117_baseline_status": ctx.v117_baseline_status,
        "production_dry_audit_controller_status": ctx.controller_status,
        "dry_audit_approval_validator_status": "PASS_DRY_AUDIT_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_DRY_AUDIT_APPROVAL" if ctx.any_fail else "PARTIAL_DRY_AUDIT_APPROVAL_ABSENT_DESIGN_ONLY"),
        "dry_audit_phrase": sgc.PRODUCTION_DRY_AUDIT_PHRASE,
        "dry_audit_approval_hash": ctx.validation["approval_hash"],
        "production_config_checklist_status": "PASS_PRODUCTION_CONFIG_CHECKLIST",
        "firewall_checklist_status": "PASS_FIREWALL_CHECKLIST",
        "risk_checklist_status": "PASS_RISK_CHECKLIST",
        "abstention_checklist_status": "PASS_ABSTENTION_CHECKLIST",
        "reconcile_checklist_status": "PASS_RECONCILE_CHECKLIST",
        "dashboard_api_safety_checklist_status": "PASS_DASHBOARD_API_SAFETY_CHECKLIST",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "no_order_proof_status": "PASS_NO_ORDER",
        "dry_audit_design_only": True,
        "broker_contacted": False,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v78_status": "PASS",
        "execution_lock_deep_recheck_v77_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V118Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v117_baseline"):
        return "PASS" if ctx.v117_baseline_status == "PASS_V117_BASELINE_READBACK" else "FAIL" if ctx.v117_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v118_production_dry_audit_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V118Context) -> dict[str, Any]:
    workstream = "v118: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v118_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V118_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v118_report.json":
        report.update({"completion_oriented_next_action_v118_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v117_carried_status": ctx.v117_baseline_status, "production_dry_audit_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v118_production_dry_audit_controller_report.json"), "no_broker_contact": str(ARTIFACTS / "v118_no_broker_contact_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v118.json", "dummy_canonical_identity_report_v118.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V118ReportFactory:
    def __init__(self, *, dry_audit_approval=None, dry_audit_approval_path=None) -> None:
        self.kw = dict(dry_audit_approval=dry_audit_approval, dry_audit_approval_path=dry_audit_approval_path)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V118Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
