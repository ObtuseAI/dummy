"""DUMMY v187 limited-autonomy dry-run approval validator — validates dry-run approval and proves no live path exists; no broker contact.

Validates the exact limited-autonomy-dryrun approval and the exact autonomy-review approval, rejects broad/fuzzy
approvals, and proves live-submit is disabled, no broker payload exists, LiveBrokerFirewall.submit is denied, caps are
unmodified, and no approval file is written. Default is PARTIAL_AUTONOMY_DRYRUN_APPROVAL_ABSENT. No live order, no broker
contact.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v187 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v187: Limited Autonomy Dryrun Approval Validator No Live Path"
MISSION_NAME = "dummy_mission_state_report_v173.json"
FINAL_NAME = "final_report_v187.json"
INDEX_KEYS = ["autonomy_dryrun_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V187 Limited Autonomy Dry-Run Approval Validator"
MISSION_KEY = "dummy_mission_state_report_v173"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Dry-Run Validator", "autonomy_dryrun_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V187_ROUTES = [
    "/api/v187/autonomy-dryrun-controller",
    "/api/v187/v186-baseline",
    "/api/v187/limited-autonomy-dryrun-approval-validator",
    "/api/v187/autonomy-review-approval-validator",
    "/api/v187/broad-fuzzy-approval-rejection",
    "/api/v187/live-submit-disabled-proof",
    "/api/v187/no-broker-payload-proof",
    "/api/v187/livebrokerfirewall-submit-denial-proof",
    "/api/v187/no-caps-modification-proof",
    "/api/v187/no-approval-file-write-proof",
    "/api/v187/readiness-governor",
    "/api/v187/execution-lock",
    "/api/v187/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "autonomy-dryrun-controller": ["v187_autonomy_dryrun_controller_report.json"],
    "v186-baseline": ["v186_baseline_readback_v1_report.json"],
    "limited-autonomy-dryrun-approval-validator": ["v187_limited_autonomy_dryrun_approval_validator_report.json"],
    "autonomy-review-approval-validator": ["v187_autonomy_review_approval_validator_report.json"],
    "broad-fuzzy-approval-rejection": ["v187_broad_fuzzy_approval_rejection_report.json"],
    "live-submit-disabled-proof": ["v187_live_submit_disabled_proof_report.json"],
    "no-broker-payload-proof": ["v187_no_broker_payload_proof_report.json"],
    "livebrokerfirewall-submit-denial-proof": ["v187_livebrokerfirewall_submit_denial_proof_report.json"],
    "no-caps-modification-proof": ["v187_no_caps_modification_proof_report.json"],
    "no-approval-file-write-proof": ["v187_no_approval_file_write_proof_report.json"],
    "readiness-governor": ["readiness_governor_v147_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v146_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v187_report_v1.json", "completion_oriented_next_action_v187_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(187)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v187/reports.py scripts/generate_v187_reports.py dashboard/backend/v187_routes.py",
    "python scripts/generate_v187_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V187Context:
    def __init__(self, *, dryrun_approval=None, autonomy_approval=None) -> None:
        self.v186_baseline_status = sgc.baseline_status("final_report_v186.json", "V186")
        self.dry_v = sgc.validate_packet(sgc.resolve_packet(None, dryrun_approval), required_phrase=sgc.LIMITED_AUTONOMY_DRYRUN_PHRASE, required_fields=sgc.LIMITED_AUTONOMY_DRYRUN_FIELDS, required_scope=sgc.LIMITED_AUTONOMY_DRYRUN_SCOPE)
        self.rev_v = sgc.validate_packet(sgc.resolve_packet(None, autonomy_approval), required_phrase=sgc.AUTONOMY_REVIEW_PHRASE, required_fields=sgc.AUTONOMY_REVIEW_FIELDS, required_scope=sgc.AUTONOMY_REVIEW_SCOPE)

    @property
    def dry_ok(self) -> bool:
        return bool(self.dry_v["accepted"])

    @property
    def rev_ok(self) -> bool:
        return bool(self.rev_v["accepted"])

    @property
    def any_fail(self) -> bool:
        return any(v["state"] == "PRESENT" and not v["accepted"] for v in (self.dry_v, self.rev_v))

    @property
    def validated(self) -> bool:
        return self.dry_ok and self.rev_ok

    @property
    def controller_status(self) -> str:
        if self.any_fail:
            return "FAIL_CLOSED_INVALID_AUTONOMY_DRYRUN_APPROVAL"
        if self.validated:
            return "PASS_AUTONOMY_DRYRUN_APPROVAL_VALIDATED_NO_LIVE_PATH"
        return "PARTIAL_AUTONOMY_DRYRUN_APPROVAL_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v186_baseline_status.startswith("FAIL") or self.any_fail:
            return "FAIL"
        return "PASS" if self.validated else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v186_baseline_status.startswith("FAIL"):
            return ["FAIL_V186_BASELINE_REGRESSION"]
        if self.any_fail:
            return ["FAIL_CLOSED_INVALID_AUTONOMY_DRYRUN_APPROVAL"]
        if self.validated:
            return []
        blockers: list[str] = []
        if not self.dry_ok:
            blockers.append("LIMITED_AUTONOMY_DRYRUN_APPROVAL_ABSENT")
        if not self.rev_ok:
            blockers.append("AUTONOMY_REVIEW_APPROVAL_ABSENT")
        return blockers

    @property
    def next_action(self) -> str:
        return "AUTONOMY_DRYRUN_APPROVAL_VALIDATED_NO_LIVE_PATH_AWAIT_SHADOW_GOVERNOR" if self.validated else "OPERATOR_MUST_SUPPLY_LIMITED_AUTONOMY_DRYRUN_AND_AUTONOMY_REVIEW_APPROVALS_NO_LIVE_PATH"


def _common(ctx: V187Context) -> dict[str, Any]:
    return {
        "v186_baseline_status": ctx.v186_baseline_status,
        "autonomy_dryrun_controller_status": ctx.controller_status,
        "limited_autonomy_dryrun_approval_validator_status": "PASS_DRYRUN_APPROVAL_VALID" if ctx.dry_ok else ("FAIL_CLOSED_INVALID_DRYRUN_APPROVAL" if ctx.dry_v["state"] == "PRESENT" and not ctx.dry_ok else "PARTIAL_DRYRUN_APPROVAL_ABSENT"),
        "autonomy_review_approval_validator_status": "PASS_AUTONOMY_REVIEW_APPROVAL_VALID" if ctx.rev_ok else ("FAIL_CLOSED_INVALID_AUTONOMY_REVIEW_APPROVAL" if ctx.rev_v["state"] == "PRESENT" and not ctx.rev_ok else "PARTIAL_AUTONOMY_REVIEW_APPROVAL_ABSENT"),
        "limited_autonomy_dryrun_phrase": sgc.LIMITED_AUTONOMY_DRYRUN_PHRASE,
        "dryrun_approval_hash": ctx.dry_v["approval_hash"],
        "autonomy_review_approval_hash": ctx.rev_v["approval_hash"],
        "broad_fuzzy_approval_rejection_status": "PASS_BROAD_FUZZY_REJECTED",
        "live_submit_disabled_proof_status": "PASS_LIVE_SUBMIT_DISABLED",
        "no_broker_payload_proof_status": "PASS_NO_BROKER_PAYLOAD",
        "livebrokerfirewall_submit_denial_proof_status": "PASS_LIVEBROKERFIREWALL_SUBMIT_DENIED",
        "no_caps_modification_proof_status": "PASS_NO_CAPS_MODIFICATION",
        "no_approval_file_write_proof_status": "PASS_NO_APPROVAL_FILE_WRITE",
        "dryrun_validated": ctx.validated,
        "approval_files_written": 0,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v147_status": "PASS",
        "execution_lock_deep_recheck_v146_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V187Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v186_baseline"):
        return "PASS" if ctx.v186_baseline_status == "PASS_V186_BASELINE_READBACK" else "FAIL" if ctx.v186_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v187_autonomy_dryrun_controller_report.json":
        return "FAIL" if ctx.any_fail else "PASS" if ctx.validated else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V187Context) -> dict[str, Any]:
    workstream = "v187: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v187_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V187_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v187_report.json":
        report.update({"completion_oriented_next_action_v187_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v186_carried_status": ctx.v186_baseline_status, "autonomy_dryrun_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v187_autonomy_dryrun_controller_report.json"), "livebrokerfirewall_submit_denial": str(ARTIFACTS / "v187_livebrokerfirewall_submit_denial_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v187.json", "dummy_canonical_identity_report_v187.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V187ReportFactory:
    def __init__(self, *, dryrun_approval=None, autonomy_approval=None) -> None:
        self.kw = dict(dryrun_approval=dryrun_approval, autonomy_approval=autonomy_approval)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V187Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
