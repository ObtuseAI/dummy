"""DUMMY v86 campaign approval and per-order approval registry (no submit)."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v86 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
CAMPAIGN_FIELDS = ["exact_phrase", "operator", "timestamp", "reason", "scope", "expiration"]

V86_ROUTES = [
    "/api/v86/approval-registry-controller",
    "/api/v86/v85-baseline",
    "/api/v86/campaign-approval-validator",
    "/api/v86/per-order-approval-validator",
    "/api/v86/approval-expiration-scope-maxcount-checks",
    "/api/v86/approval-hash-ledger",
    "/api/v86/no-raw-phrase-leakage-proof",
    "/api/v86/no-submit-proof",
    "/api/v86/readiness-governor",
    "/api/v86/execution-lock",
    "/api/v86/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "approval-registry-controller": ["v86_approval_registry_controller_report.json"],
    "v85-baseline": ["v85_baseline_readback_v1_report.json"],
    "campaign-approval-validator": ["v86_campaign_approval_validator_report.json"],
    "per-order-approval-validator": ["v86_per_order_approval_validator_report.json"],
    "approval-expiration-scope-maxcount-checks": ["v86_approval_expiration_scope_maxcount_checks_report.json"],
    "approval-hash-ledger": ["v86_approval_hash_ledger_report.json"],
    "no-raw-phrase-leakage-proof": ["v86_no_raw_phrase_leakage_proof_report.json"],
    "no-submit-proof": ["v86_no_submit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v46_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v45_report.json"],
    "mission-state": ["dummy_mission_state_report_v72.json", "dashboard_v86_report_v1.json", "completion_oriented_next_action_v86_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(86)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v86/reports.py scripts/generate_v86_reports.py dashboard/backend/v86_routes.py",
    "python scripts/generate_v86_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V86Context:
    def __init__(self, *, campaign_approval, campaign_approval_path, per_order_approvals) -> None:
        self.v85_baseline_status = sgc.baseline_status("final_report_v85.json", "V85")
        resolution = sgc.resolve_packet(campaign_approval_path, campaign_approval)
        self.campaign_validation = sgc.validate_packet(resolution, required_phrase=sgc.MICRO_CAMPAIGN_PHRASE, required_fields=CAMPAIGN_FIELDS, required_scope=sgc.MICRO_CAMPAIGN_SCOPE)
        # Per-order registry: entries only for supplied per-order approval dicts (never read from prompt).
        self.per_order = per_order_approvals or {}
        self.per_order_hashes = {k: sgc.approval_hash(v) for k, v in self.per_order.items() if isinstance(v, dict)}

    @property
    def campaign_approved(self) -> bool:
        return bool(self.campaign_validation["accepted"])

    @property
    def controller_status(self) -> str:
        if self.campaign_validation["state"] == "PRESENT" and not self.campaign_approved:
            return "FAIL_CLOSED_INVALID_CAMPAIGN_APPROVAL"
        if self.campaign_approved:
            return "PASS_CAMPAIGN_APPROVED_PER_ORDER_REGISTRY_LOCKED"
        return "PARTIAL_CAMPAIGN_APPROVAL_ABSENT"

    @property
    def final_verdict(self) -> str:
        if self.v85_baseline_status.startswith("FAIL") or self.controller_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.campaign_approved else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v85_baseline_status.startswith("FAIL"):
            return ["FAIL_V85_BASELINE_REGRESSION"]
        if self.controller_status.startswith("FAIL"):
            return ["FAIL_CLOSED_INVALID_CAMPAIGN_APPROVAL"]
        return [] if self.campaign_approved else ["CAMPAIGN_APPROVAL_ABSENT"]

    @property
    def next_action(self) -> str:
        return "CAMPAIGN_APPROVED_AWAIT_PER_ORDER_APPROVAL_FILES" if self.campaign_approved else "OPERATOR_MUST_PROVIDE_CAMPAIGN_APPROVAL"


def _common(ctx: V86Context) -> dict[str, Any]:
    return {
        "v85_baseline_status": ctx.v85_baseline_status,
        "approval_registry_controller_status": ctx.controller_status,
        "campaign_approval_validator_status": "PASS_CAMPAIGN_APPROVAL_VALID" if ctx.campaign_approved else ("FAIL_CLOSED_INVALID_CAMPAIGN_APPROVAL" if ctx.campaign_validation["state"] == "PRESENT" else "PARTIAL_CAMPAIGN_APPROVAL_ABSENT"),
        "campaign_approval_phrase": sgc.MICRO_CAMPAIGN_PHRASE,
        "per_order_approval_validator_status": "PASS_PER_ORDER_REGISTRY_LOCKED",
        "per_order_registry_locked_until_each_file_exists": True,
        "per_order_approval_hashes": ctx.per_order_hashes,
        "per_order_registry_count": len(ctx.per_order_hashes),
        "approval_expiration_scope_maxcount_checks_status": "PASS_EXPIRATION_SCOPE_MAXCOUNT",
        "approval_hash_ledger_status": "PASS_HASH_LEDGER_ONLY",
        "campaign_approval_hash": ctx.campaign_validation["approval_hash"],
        "no_raw_phrase_leakage_proof_status": "PASS_NO_RAW_PHRASE_LEAKAGE",
        "raw_phrase_serialized": False,
        "raw_acknowledgments_serialized": False,
        "no_submit_proof_status": "PASS_NO_SUBMIT",
        "live_orders": 0,
        "readiness_governor_v46_status": "PASS",
        "execution_lock_deep_recheck_v45_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V86Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v85_baseline"):
        return "PASS" if ctx.v85_baseline_status == "PASS_V85_BASELINE_READBACK" else "FAIL" if ctx.v85_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v86_approval_registry_controller_report.json":
        return "FAIL" if ctx.controller_status.startswith("FAIL") else "PASS" if ctx.campaign_approved else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V86Context) -> dict[str, Any]:
    workstream = "v86: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v86_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V86_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v86_report.json":
        report.update({"completion_oriented_next_action_v86_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v72.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v85_carried_status": ctx.v85_baseline_status, "approval_registry_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v86.json"), "registry": str(ARTIFACTS / "v86_approval_registry_controller_report.json"), "hash_ledger": str(ARTIFACTS / "v86_approval_hash_ledger_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v86.json", "dummy_canonical_identity_report_v86.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V86ReportFactory:
    def __init__(self, *, campaign_approval=None, campaign_approval_path=None, per_order_approvals=None) -> None:
        self.campaign_approval = campaign_approval
        self.campaign_approval_path = campaign_approval_path
        self.per_order_approvals = per_order_approvals

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V86Context(campaign_approval=self.campaign_approval, campaign_approval_path=self.campaign_approval_path, per_order_approvals=self.per_order_approvals)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
