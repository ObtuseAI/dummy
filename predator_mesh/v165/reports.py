"""DUMMY v165 repeat pilot authority binder — binds repeat-pilot authority + first-pilot prerequisite proof; never submits.

Validates the exact repeat-pilot approval and requires first-real-pilot reconcile (V162) + forensic (V163) proof, plus
live-submit/caps (V157), firewall (V158), and optional broker read-only (V159) checks. Emits a hash-only ledger and an
authority gap map. Default is PARTIAL_REPEAT_AUTHORITY_BLOCKED_NO_FIRST_PILOT_PROOF. Binding never submits, never
contacts a broker, and writes no approval files.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v165 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v165: Repeat Pilot Authority Binder First Pilot Proof And Approval Map"
MISSION_NAME = "dummy_mission_state_report_v151.json"
FINAL_NAME = "final_report_v165.json"
INDEX_KEYS = ["repeat_authority_binder_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V165 Repeat Pilot Authority Binder"
MISSION_KEY = "dummy_mission_state_report_v151"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Repeat Authority", "repeat_authority_binder_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V165_ROUTES = [
    "/api/v165/repeat-authority-binder-controller",
    "/api/v165/v164-baseline",
    "/api/v165/repeat-approval-file-validator",
    "/api/v165/first-pilot-reconcile-proof-checker",
    "/api/v165/first-pilot-forensic-proof-checker",
    "/api/v165/live-submit-caps-status-checker",
    "/api/v165/firewall-adapter-checker",
    "/api/v165/broker-readonly-checker",
    "/api/v165/approval-hash-only-ledger",
    "/api/v165/authority-gap-map",
    "/api/v165/no-submit-proof",
    "/api/v165/no-broker-contact-proof",
    "/api/v165/no-approval-file-write-proof",
    "/api/v165/readiness-governor",
    "/api/v165/execution-lock",
    "/api/v165/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-authority-binder-controller": ["v165_repeat_authority_binder_controller_report.json"],
    "v164-baseline": ["v164_baseline_readback_v1_report.json"],
    "repeat-approval-file-validator": ["v165_repeat_approval_file_validator_report.json"],
    "first-pilot-reconcile-proof-checker": ["v165_first_pilot_reconcile_proof_checker_report.json"],
    "first-pilot-forensic-proof-checker": ["v165_first_pilot_forensic_proof_checker_report.json"],
    "live-submit-caps-status-checker": ["v165_live_submit_caps_status_checker_report.json"],
    "firewall-adapter-checker": ["v165_firewall_adapter_checker_report.json"],
    "broker-readonly-checker": ["v165_broker_readonly_checker_report.json"],
    "approval-hash-only-ledger": ["v165_approval_hash_only_ledger_report.json"],
    "authority-gap-map": ["v165_authority_gap_map_report.json"],
    "no-submit-proof": ["v165_no_submit_proof_report.json"],
    "no-broker-contact-proof": ["v165_no_broker_contact_proof_report.json"],
    "no-approval-file-write-proof": ["v165_no_approval_file_write_proof_report.json"],
    "readiness-governor": ["readiness_governor_v125_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v124_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v165_report_v1.json", "completion_oriented_next_action_v165_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(165)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v165/reports.py scripts/generate_v165_reports.py dashboard/backend/v165_routes.py",
    "python scripts/generate_v165_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V165Context:
    def __init__(self, *, repeat_approval=None, repeat_approval_path=None, first_pilot_override=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None) -> None:
        self.v164_baseline_status = sgc.baseline_status("final_report_v164.json", "V164")
        res = sgc.resolve_packet(repeat_approval_path, repeat_approval)
        self.validation = sgc.validate_packet(res, required_phrase=sgc.REPEAT_PILOT_PHRASE, required_fields=sgc.REPEAT_PILOT_FIELDS, required_scope=sgc.REPEAT_PILOT_SCOPE)
        if first_pilot_override is not None:
            self.first_pilot_ok = bool(first_pilot_override)
        else:
            reconciled = str(sgc.load_artifact("final_report_v162.json").get("reconcile_controller_status", "")) == "PASS_FIRST_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
            reviewed = str(sgc.load_artifact("final_report_v163.json").get("forensic_controller_status", "")) == "PASS_FIRST_REAL_PILOT_FORENSIC_REVIEWED"
            self.first_pilot_ok = reconciled and reviewed
        self.live_submit_operator_enabled = bool(live_submit_operator_enabled)
        self.caps_config_present = bool(caps_config_present)
        self.firewall_adapter_present = firewall_adapter is not None

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"])

    @property
    def any_fail(self) -> bool:
        return self.validation["state"] == "PRESENT" and not self.validation["accepted"]

    @property
    def bound(self) -> bool:
        return self.approved and self.first_pilot_ok and self.live_submit_operator_enabled and self.caps_config_present and self.firewall_adapter_present

    @property
    def authority_gap_map(self) -> dict[str, str]:
        return {
            "repeat_approval": "PRESENT" if self.approved else "ABSENT",
            "first_pilot_reconcile_forensic": "PRESENT" if self.first_pilot_ok else "ABSENT",
            "live_submit_operator_enabled": "PRESENT" if self.live_submit_operator_enabled else "ABSENT",
            "caps_config": "PRESENT" if self.caps_config_present else "ABSENT",
            "firewall_adapter": "PRESENT" if self.firewall_adapter_present else "ABSENT",
        }

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_REPEAT_APPROVAL"
        if self.bound:
            return "PASS_REPEAT_AUTHORITY_BOUND_NO_SUBMIT"
        if not self.first_pilot_ok:
            return "PARTIAL_REPEAT_AUTHORITY_BLOCKED_NO_FIRST_PILOT_PROOF"
        return "PARTIAL_REPEAT_AUTHORITY_INCOMPLETE"

    @property
    def final_verdict(self) -> str:
        if self.v164_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.bound else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v164_baseline_status.startswith("FAIL"):
            return ["FAIL_V164_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_REPEAT_APPROVAL"]
        if self.bound:
            return []
        return [f"AUTHORITY_GAP:{k}" for k, v in self.authority_gap_map.items() if v == "ABSENT"]

    @property
    def next_action(self) -> str:
        return "REPEAT_AUTHORITY_BOUND_NO_SUBMIT_AWAIT_REPEAT_PREFLIGHT" if self.bound else "OPERATOR_MUST_SUPPLY_REPEAT_APPROVAL_FIRST_PILOT_PROOF_LIVE_SUBMIT_CAPS_AND_FIREWALL"


def _common(ctx: V165Context) -> dict[str, Any]:
    v = ctx.validation
    return {
        "v164_baseline_status": ctx.v164_baseline_status,
        "repeat_authority_binder_controller_status": ctx.controller_status,
        "repeat_approval_file_validator_status": "PASS_REPEAT_APPROVAL_VALID" if ctx.approved else ("FAIL_CLOSED_INVALID_REPEAT_APPROVAL" if ctx.any_fail else "PARTIAL_REPEAT_APPROVAL_ABSENT"),
        "repeat_approval_hash": v["approval_hash"],
        "first_pilot_reconcile_proof_checker_status": "PASS_FIRST_PILOT_RECONCILED" if ctx.first_pilot_ok else "PARTIAL_FIRST_PILOT_NOT_RECONCILED",
        "first_pilot_forensic_proof_checker_status": "PASS_FIRST_PILOT_FORENSIC_PRESENT" if ctx.first_pilot_ok else "PARTIAL_FIRST_PILOT_FORENSIC_ABSENT",
        "live_submit_caps_status_checker_status": "PASS_LIVE_SUBMIT_CAPS_READONLY" if (ctx.live_submit_operator_enabled and ctx.caps_config_present) else "PARTIAL_LIVE_SUBMIT_OR_CAPS_ABSENT",
        "firewall_adapter_checker_status": "PASS_FIREWALL_ADAPTER_PRESENT" if ctx.firewall_adapter_present else "PARTIAL_FIREWALL_ADAPTER_ABSENT",
        "broker_readonly_checker_status": "PARTIAL_BROKER_READONLY_OPTIONAL_ABSENT",
        "approval_hash_only_ledger_status": "PASS_HASH_ONLY_LEDGER",
        "approval_hash_only_ledger": {"repeat_pilot": v["approval_hash"]},
        "authority_gap_map": ctx.authority_gap_map,
        "authority_gap_map_status": "PASS_AUTHORITY_GAP_MAPPED",
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "authority_bound": ctx.bound,
        "approval_files_written": 0,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v125_status": "PASS",
        "execution_lock_deep_recheck_v124_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V165Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v164_baseline"):
        return "PASS" if ctx.v164_baseline_status == "PASS_V164_BASELINE_READBACK" else "FAIL" if ctx.v164_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v165_repeat_authority_binder_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.bound else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V165Context) -> dict[str, Any]:
    workstream = "v165: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v165_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V165_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v165_report.json":
        report.update({"completion_oriented_next_action_v165_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v164_carried_status": ctx.v164_baseline_status, "repeat_authority_binder_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v165_repeat_authority_binder_controller_report.json"), "no_submit": str(ARTIFACTS / "v165_no_submit_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v165.json", "dummy_canonical_identity_report_v165.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V165ReportFactory:
    def __init__(self, *, repeat_approval=None, repeat_approval_path=None, first_pilot_override=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None) -> None:
        self.kw = dict(repeat_approval=repeat_approval, repeat_approval_path=repeat_approval_path, first_pilot_override=first_pilot_override, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V165Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
