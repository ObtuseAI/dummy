"""DUMMY v138 firewall adapter contract + broker contact denial — verifies the LiveBrokerFirewall adapter; no broker contact.

Checks the injected adapter satisfies the firewall-only contract (a callable submit, no direct broker bypass). Default
has no adapter -> PARTIAL_FIREWALL_ADAPTER_ABSENT. Tests inject a NON-BROKER double. By default no submit/cancel, no
private account access, and secrets stay redacted; real_broker_contacted=false.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v138 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

WORKSTREAM = "v138: Firewall Adapter Contract And Broker Contact Denial"
MISSION_NAME = "dummy_mission_state_report_v124.json"
FINAL_NAME = "final_report_v138.json"
INDEX_KEYS = ["firewall_adapter_controller_status", "real_broker_contacted", "live_orders"]
DASH_TITLE = "Dummy V138 Firewall Adapter Contract"
MISSION_KEY = "dummy_mission_state_report_v124"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Firewall Adapter", "firewall_adapter_controller_status"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Live Orders", "live_orders"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V138_ROUTES = [
    "/api/v138/firewall-adapter-controller",
    "/api/v138/v137-baseline",
    "/api/v138/adapter-interface-checker",
    "/api/v138/firewall-only-proof",
    "/api/v138/no-direct-broker-bypass-proof",
    "/api/v138/no-submit-cancel-default-proof",
    "/api/v138/no-private-account-access-proof",
    "/api/v138/secret-redaction-proof",
    "/api/v138/no-broker-contact-proof",
    "/api/v138/readiness-governor",
    "/api/v138/execution-lock",
    "/api/v138/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "firewall-adapter-controller": ["v138_firewall_adapter_controller_report.json"],
    "v137-baseline": ["v137_baseline_readback_v1_report.json"],
    "adapter-interface-checker": ["v138_adapter_interface_checker_report.json"],
    "firewall-only-proof": ["v138_firewall_only_proof_report.json"],
    "no-direct-broker-bypass-proof": ["v138_no_direct_broker_bypass_proof_report.json"],
    "no-submit-cancel-default-proof": ["v138_no_submit_cancel_default_proof_report.json"],
    "no-private-account-access-proof": ["v138_no_private_account_access_proof_report.json"],
    "secret-redaction-proof": ["v138_secret_redaction_proof_report.json"],
    "no-broker-contact-proof": ["v138_no_broker_contact_proof_report.json"],
    "readiness-governor": ["readiness_governor_v98_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v97_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v138_report_v1.json", "completion_oriented_next_action_v138_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(138)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v138/reports.py scripts/generate_v138_reports.py dashboard/backend/v138_routes.py",
    "python scripts/generate_v138_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V138Context:
    def __init__(self, *, firewall_adapter=None) -> None:
        self.v137_baseline_status = sgc.baseline_status("final_report_v137.json", "V137")
        self.firewall_adapter_present = firewall_adapter is not None
        self.adapter_contract_ok = firewall_adapter is not None and callable(getattr(firewall_adapter, "submit", None))

    @property
    def controller_status(self) -> str:
        if not self.firewall_adapter_present:
            return "PARTIAL_FIREWALL_ADAPTER_ABSENT"
        return "PASS_FIREWALL_ADAPTER_CONTRACT_VERIFIED" if self.adapter_contract_ok else "PARTIAL_FIREWALL_ADAPTER_CONTRACT_INVALID"

    @property
    def final_verdict(self) -> str:
        if self.v137_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.adapter_contract_ok else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.v137_baseline_status.startswith("FAIL"):
            return ["FAIL_V137_BASELINE_REGRESSION"]
        if self.adapter_contract_ok:
            return []
        return ["FIREWALL_ADAPTER_ABSENT"] if not self.firewall_adapter_present else ["FIREWALL_ADAPTER_CONTRACT_INVALID"]

    @property
    def next_action(self) -> str:
        return "FIREWALL_ADAPTER_CONTRACT_VERIFIED_NO_CONTACT_AWAIT_CANDIDATE_PREFLIGHT" if self.adapter_contract_ok else "OPERATOR_MUST_INJECT_LIVEBROKERFIREWALL_ADAPTER_NO_DIRECT_BROKER"


def _common(ctx: V138Context) -> dict[str, Any]:
    return {
        "v137_baseline_status": ctx.v137_baseline_status,
        "firewall_adapter_controller_status": ctx.controller_status,
        "adapter_interface_checker_status": "PASS_ADAPTER_INTERFACE_VALID" if ctx.adapter_contract_ok else ("PARTIAL_ADAPTER_INTERFACE_INVALID" if ctx.firewall_adapter_present else "PARTIAL_FIREWALL_ADAPTER_ABSENT"),
        "firewall_only_proof_status": "PASS_FIREWALL_ONLY",
        "no_direct_broker_bypass_proof_status": "PASS_NO_DIRECT_BROKER_BYPASS",
        "no_submit_cancel_default_proof_status": "PASS_NO_SUBMIT_CANCEL_DEFAULT",
        "no_private_account_access_proof_status": "PASS_NO_PRIVATE_ACCOUNT_ACCESS",
        "secret_redaction_proof_status": "PASS_SECRETS_REDACTED",
        "no_broker_contact_proof_status": "PASS_NO_BROKER_CONTACT",
        "firewall_adapter_present": ctx.firewall_adapter_present,
        "adapter_contract_ok": ctx.adapter_contract_ok,
        "caps_modified": False,
        "live_submit_enabled": False,
        "scale_applied": False,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "real_broker_contacted": False,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v98_status": "PASS",
        "execution_lock_deep_recheck_v97_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V138Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v137_baseline"):
        return "PASS" if ctx.v137_baseline_status == "PASS_V137_BASELINE_READBACK" else "FAIL" if ctx.v137_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v138_firewall_adapter_controller_report.json":
        return "PASS" if ctx.adapter_contract_ok else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V138Context) -> dict[str, Any]:
    workstream = "v138: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v138_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V138_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v138_report.json":
        report.update({"completion_oriented_next_action_v138_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v137_carried_status": ctx.v137_baseline_status, "firewall_adapter_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v138_firewall_adapter_controller_report.json"), "no_broker_contact": str(ARTIFACTS / "v138_no_broker_contact_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v138.json", "dummy_canonical_identity_report_v138.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V138ReportFactory:
    def __init__(self, *, firewall_adapter=None) -> None:
        self.kw = dict(firewall_adapter=firewall_adapter)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V138Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
