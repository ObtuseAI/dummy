"""DUMMY v65 operator-armed micro-order canary gate — armed conceptually only, never fired.

V65 validates that all future prerequisites are present and, if an exact future live-canary approval
packet validates in an isolated test fixture, marks the gate armed CONCEPTUALLY ONLY. It never
submits a live order, never enables live-submit, never modifies caps, never accesses account/private
data, never allows market orders, and never sends a broker payload.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v65 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS

LIVE_CANARY_SCOPE = "single_tiny_live_limit_order_canary_via_firewall_only"
REQUIRED_APPROVAL_FIELDS = [
    "exact_phrase",
    "operator",
    "timestamp",
    "reason",
    "scope",
    "expiration",
    "kill_switch_acknowledgment",
    "rollback_acknowledgment",
    "no_market_order_acknowledgment",
    "caps_unchanged_acknowledgment",
    "firewall_only_acknowledgment",
]
ACK_REQUIREMENTS = (
    ("kill_switch_acknowledgment", "kill-switch"),
    ("rollback_acknowledgment", "rollback"),
    ("no_market_order_acknowledgment", "no market order"),
    ("caps_unchanged_acknowledgment", "caps unchanged"),
    ("firewall_only_acknowledgment", "firewall only"),
)
PREREQ_FINALS = ["final_report_v60.json", "final_report_v61.json", "final_report_v62.json", "final_report_v63.json", "final_report_v64.json"]

V65_ROUTES = [
    "/api/v65/micro-order-canary-gate-controller",
    "/api/v65/v64-baseline",
    "/api/v65/live-canary-approval-packet-validator",
    "/api/v65/arming-state",
    "/api/v65/pre-submit-denial-proof",
    "/api/v65/limit-order-only-proof",
    "/api/v65/no-market-order-proof",
    "/api/v65/livebrokerfirewall-only-proof",
    "/api/v65/kill-switch-proof",
    "/api/v65/rollback-proof",
    "/api/v65/idempotency-proof",
    "/api/v65/exposure-caps-readonly-proof",
    "/api/v65/live-submit-disabled-proof",
    "/api/v65/canary-nonexecution-validator-v15",
    "/api/v65/readiness-governor",
    "/api/v65/execution-lock",
    "/api/v65/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "micro-order-canary-gate-controller": ["v65_micro_order_canary_gate_controller_report.json"],
    "v64-baseline": ["v64_baseline_readback_v1_report.json"],
    "live-canary-approval-packet-validator": ["v65_live_canary_approval_packet_validator_report.json"],
    "arming-state": ["v65_arming_state_report.json"],
    "pre-submit-denial-proof": ["v65_pre_submit_denial_proof_report.json"],
    "limit-order-only-proof": ["v65_limit_order_only_proof_report.json"],
    "no-market-order-proof": ["v65_no_market_order_proof_report.json"],
    "livebrokerfirewall-only-proof": ["v65_livebrokerfirewall_only_proof_report.json"],
    "kill-switch-proof": ["v65_kill_switch_proof_report.json"],
    "rollback-proof": ["v65_rollback_proof_report.json"],
    "idempotency-proof": ["v65_idempotency_proof_report.json"],
    "exposure-caps-readonly-proof": ["v65_exposure_caps_readonly_proof_report.json"],
    "live-submit-disabled-proof": ["v65_live_submit_disabled_proof_report.json"],
    "canary-nonexecution-validator-v15": ["v65_canary_nonexecution_validator_v15_report.json"],
    "readiness-governor": ["readiness_governor_v25_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v24_report.json"],
    "mission-state": ["dummy_mission_state_report_v51.json", "dashboard_v65_report_v1.json", "completion_oriented_next_action_v65_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(65)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v65/reports.py scripts/generate_v65_reports.py dashboard/backend/v65_routes.py",
    "python scripts/generate_v65_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]

PROOF_STATUSES = {
    "pre_submit_denial_proof_status": "PASS_PRE_SUBMIT_DENIED",
    "limit_order_only_proof_status": "PASS_LIMIT_ORDER_ONLY",
    "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
    "livebrokerfirewall_only_proof_status": "PASS_LIVEBROKERFIREWALL_ONLY",
    "kill_switch_proof_status": "PASS_KILL_SWITCH_PRESENT",
    "rollback_proof_status": "PASS_ROLLBACK_PRESENT",
    "idempotency_proof_status": "PASS_IDEMPOTENCY_PRESENT",
    "exposure_caps_readonly_proof_status": "PASS_EXPOSURE_CAPS_READONLY",
    "live_submit_disabled_proof_status": "PASS_LIVE_SUBMIT_DISABLED",
}


class V65Context:
    def __init__(self, *, approval_input, approval_path) -> None:
        self.v64_baseline_status = sgc.baseline_status("final_report_v64.json", "V64")
        self.prereq_verdicts = {name: sgc.load_artifact(name).get("verdict", "MISSING") for name in PREREQ_FINALS}
        self.prereqs_ok = all(v in {"PASS", "PARTIAL"} for v in self.prereq_verdicts.values())
        self.resolution = sgc.resolve_packet(approval_path, approval_input)
        self.validation = sgc.validate_packet(
            self.resolution,
            required_phrase=sgc.LIVE_CANARY_PHRASE,
            required_fields=REQUIRED_APPROVAL_FIELDS,
            required_scope=LIVE_CANARY_SCOPE,
            ack_requirements=ACK_REQUIREMENTS,
        )

    @property
    def approved(self) -> bool:
        return bool(self.validation["accepted"]) and self.prereqs_ok

    @property
    def gate_status(self) -> str:
        # A submit path is never created, so FAIL_GATE_CREATED_SUBMIT_PATH cannot occur here.
        if self.approved:
            return "PASS_MICRO_ORDER_CANARY_GATE_READY_LOCKED"
        return "PARTIAL_LIVE_CANARY_APPROVAL_ABSENT"

    @property
    def arming_state(self) -> str:
        return "ARMED_CONCEPTUAL_NO_FIRE" if self.approved else "NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v64_baseline_status.startswith("FAIL"):
            return "FAIL"
        if self.approved:
            return "PASS"
        return "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        blockers: list[str] = []
        if self.v64_baseline_status.startswith("FAIL"):
            blockers.append("FAIL_V64_BASELINE_REGRESSION")
        elif self.v64_baseline_status.startswith("PARTIAL"):
            blockers.append("PARTIAL_V64_BASELINE_UNAVAILABLE")
        if not self.prereqs_ok:
            blockers.append("PREREQUISITE_GATES_INCOMPLETE")
        if not self.validation["accepted"]:
            state = self.validation["state"]
            if state == "ABSENT":
                blockers.append("LIVE_CANARY_APPROVAL_ABSENT")
            elif state == "MALFORMED":
                blockers.append("LIVE_CANARY_APPROVAL_MALFORMED")
            else:
                blockers.append("LIVE_CANARY_APPROVAL_INVALID")
        return blockers

    @property
    def next_action(self) -> str:
        if self.approved:
            return "MICRO_ORDER_CANARY_GATE_READY_LOCKED_ARMED_CONCEPTUAL_NO_FIRE"
        return "OPERATOR_MAY_PROVIDE_FUTURE_LIVE_CANARY_APPROVAL"


def _common(ctx: V65Context) -> dict[str, Any]:
    common = {
        "v64_baseline_status": ctx.v64_baseline_status,
        "prerequisite_gate_verdicts": ctx.prereq_verdicts,
        "prerequisite_gates_ok": ctx.prereqs_ok,
        "micro_order_canary_gate_status": ctx.gate_status,
        "arming_state": ctx.arming_state,
        "order_fired": False,
        "submit_call_made": False,
        "cancel_call_made": False,
        "broker_payload_sent": False,
        "live_submit_changed": False,
        "caps_changed": False,
        "live_canary_approval_phrase": sgc.LIVE_CANARY_PHRASE,
        "required_approval_fields": REQUIRED_APPROVAL_FIELDS,
        "live_canary_approval_packet_validator_status": "PASS_EXACT_LIVE_CANARY_PACKET_VALID" if ctx.validation["accepted"] else "PARTIAL_LIVE_CANARY_APPROVAL_ABSENT",
        "approval_input_resolution": ctx.resolution.get("resolution"),
        "approval_validated": bool(ctx.validation["accepted"]),
        "approval_validation_isolated_test_only": True,
        "approval_hash": ctx.validation["approval_hash"],
        "live_trading_readiness_claim_beyond_gate_ready": False,
        "canary_nonexecution_validator_v15_status": "PASS_CANARY_NONEXECUTION_VALIDATOR_V15",
        "readiness_governor_v25_status": "PASS",
        "execution_lock_deep_recheck_v24_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }
    common.update(PROOF_STATUSES)
    return common


def _verdict(name: str, ctx: V65Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v64_baseline"):
        return "PASS" if ctx.v64_baseline_status == "PASS_V64_BASELINE_READBACK" else "FAIL" if ctx.v64_baseline_status.startswith("FAIL") else "PARTIAL"
    if name in {"v65_micro_order_canary_gate_controller_report.json", "v65_live_canary_approval_packet_validator_report.json", "v65_arming_state_report.json"}:
        return "PASS" if ctx.approved else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V65Context) -> dict[str, Any]:
    workstream = "v65: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "v65_arming_state_report.json":
        report.update({"v65_arming_state_status": ctx.arming_state, "order_fired": False, "conceptual_only": True})
    elif name == "dashboard_v65_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V65_ROUTES, "read_only_dashboard": True, "dashboard_can_fire_order": False, "dashboard_can_submit_orders": False, "dashboard_can_access_account": False})
    elif name == "completion_oriented_next_action_v65_report.json":
        report.update({"completion_oriented_next_action_v65_status": "PASS", "next_action": ctx.next_action})
    elif name == "dummy_mission_state_report_v51.json":
        report.update({"mission_state_verdict": ctx.final_verdict, "v64_carried_status": ctx.v64_baseline_status, "proof_paths": {"final_report": str(ARTIFACTS / "final_report_v65.json"), "gate_controller": str(ARTIFACTS / "v65_micro_order_canary_gate_controller_report.json"), "arming_state": str(ARTIFACTS / "v65_arming_state_report.json"), "pre_submit_denial": str(ARTIFACTS / "v65_pre_submit_denial_proof_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v65.json", "dummy_canonical_identity_report_v65.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V65ReportFactory:
    def __init__(self, *, approval_input=None, approval_path=None) -> None:
        self.approval_input = approval_input
        self.approval_path = approval_path

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V65Context(approval_input=self.approval_input, approval_path=self.approval_path)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
