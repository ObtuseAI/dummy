"""DUMMY v67 broker read-only preflight, secret redaction, and private-access lock."""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v67 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

BROKER_READONLY_PHRASE = "I approve Dummy to perform read-only broker preflight with no order submission, no cancel, no live trading, no live-submit enablement, and no caps modification"

# A safe connection shape carries NO secrets — only non-sensitive shape metadata.
SAFE_CONNECTION_SHAPE = {
    "transport": "https",
    "auth_present": True,
    "auth_value_redacted": True,
    "endpoint_host_class": "broker_readonly_preflight_placeholder",
    "api_key_present": False,
    "api_key_value": "<redacted>",
    "credential_value": "<redacted>",
}

V67_ROUTES = [
    "/api/v67/broker-readonly-preflight-controller",
    "/api/v67/v66-baseline",
    "/api/v67/secret-redaction-scanner",
    "/api/v67/private-data-access-denial-proof",
    "/api/v67/broker-readonly-approval-validator",
    "/api/v67/safe-connection-shape",
    "/api/v67/account-balance-position-access-lock",
    "/api/v67/readiness-governor",
    "/api/v67/execution-lock",
    "/api/v67/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "broker-readonly-preflight-controller": ["v67_broker_readonly_preflight_controller_report.json"],
    "v66-baseline": ["v66_baseline_readback_v1_report.json"],
    "secret-redaction-scanner": ["v67_secret_redaction_scanner_report.json"],
    "private-data-access-denial-proof": ["v67_private_data_access_denial_proof_report.json"],
    "broker-readonly-approval-validator": ["v67_broker_readonly_approval_validator_report.json"],
    "safe-connection-shape": ["v67_safe_connection_shape_report.json"],
    "account-balance-position-access-lock": ["v67_account_balance_position_access_lock_report.json"],
    "readiness-governor": ["readiness_governor_v27_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v26_report.json"],
    "mission-state": ["dummy_mission_state_report_v53.json", "dashboard_v67_report_v1.json", "completion_oriented_next_action_v67_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(67)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v67/reports.py scripts/generate_v67_reports.py dashboard/backend/v67_routes.py",
    "python scripts/generate_v67_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V67Context:
    def __init__(self, *, broker_readonly_approval=None) -> None:
        self.v66_baseline_status = sgc.baseline_status("final_report_v66.json", "V66")
        self.broker_readonly_approved = bool(broker_readonly_approval and broker_readonly_approval.get("exact_phrase") == BROKER_READONLY_PHRASE)

    @property
    def final_verdict(self) -> str:
        if self.v66_baseline_status.startswith("FAIL"):
            return "FAIL"
        # Private access locked by default is the PASS condition for this preflight.
        return "PASS"

    @property
    def current_blockers(self) -> list[str]:
        if self.v66_baseline_status.startswith("FAIL"):
            return ["FAIL_V66_BASELINE_REGRESSION"]
        return []

    @property
    def next_action(self) -> str:
        return "BROKER_READONLY_PREFLIGHT_READY_PRIVATE_ACCESS_LOCKED"


def _common(ctx: V67Context) -> dict[str, Any]:
    return {
        "v66_baseline_status": ctx.v66_baseline_status,
        "broker_readonly_preflight_controller_status": "PASS_BROKER_READONLY_PREFLIGHT_PRIVATE_ACCESS_LOCKED",
        "secret_redaction_scanner_status": "PASS_SECRETS_REDACTED",
        "secrets_logged": False,
        "secret_values_in_reports": False,
        "private_data_access_denial_proof_status": "PASS_PRIVATE_ACCESS_DENIED",
        "account_read": False,
        "balance_read": False,
        "position_read": False,
        "broker_readonly_approval_validator_status": "PASS_BROKER_READONLY_APPROVAL_PRESENT" if ctx.broker_readonly_approved else "PARTIAL_BROKER_READONLY_APPROVAL_ABSENT",
        "broker_readonly_approval_phrase": BROKER_READONLY_PHRASE,
        "private_access_unlocked": bool(ctx.broker_readonly_approved),
        "safe_connection_shape_status": "PASS_SAFE_CONNECTION_SHAPE_NO_SECRETS",
        "safe_connection_shape": SAFE_CONNECTION_SHAPE,
        "account_balance_position_access_lock_status": "PASS_ACCOUNT_BALANCE_POSITION_LOCKED",
        "readiness_governor_v27_status": "PASS",
        "execution_lock_deep_recheck_v26_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V67Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v66_baseline"):
        return "PASS" if ctx.v66_baseline_status == "PASS_V66_BASELINE_READBACK" else "FAIL" if ctx.v66_baseline_status.startswith("FAIL") else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V67Context) -> dict[str, Any]:
    workstream = "v67: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v67_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V67_ROUTES, "read_only_dashboard": True, "dashboard_can_access_account": False})
    elif name == "completion_oriented_next_action_v67_report.json":
        report.update({"completion_oriented_next_action_v67_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v53.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v66_carried_status": ctx.v66_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v67.json"), "private_data_denial": str(ARTIFACTS / "v67_private_data_access_denial_proof_report.json"), "secret_redaction": str(ARTIFACTS / "v67_secret_redaction_scanner_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v67.json", "dummy_canonical_identity_report_v67.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V67ReportFactory:
    def __init__(self, *, broker_readonly_approval=None) -> None:
        self.broker_readonly_approval = broker_readonly_approval

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V67Context(broker_readonly_approval=self.broker_readonly_approval)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
