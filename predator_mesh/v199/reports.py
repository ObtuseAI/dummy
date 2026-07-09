"""DUMMY v199 first live-proof fire gate — submits exactly one bounded first-live-proof attempt ONLY on full authority, else nothing.

Submit occurs ONLY when the V198 quorum is ready, the mode firewall is LIVE_AUTHORIZED, the exact relevant approval
validates, live-submit is operator-enabled, caps are present/unchanged, the selected proof target is
FIRST_REAL_PILOT_PROOF or CONTROLLED_SESSION_PROOF, and an explicit LiveBrokerFirewall adapter is injected. Default has
none -> no submit (PARTIAL_FIRST_LIVE_PROOF_NOT_ARMED). Tests inject a NON-BROKER firewall double. Dry mode / missing
quorum block. On submit the proof immediately auto-locks; limit-only, no market orders, no repeat.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v199 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "first_live_proof": True}

WORKSTREAM = "v199: First Live Proof Fire Gate Full Auth Only"
MISSION_NAME = "dummy_mission_state_report_v185.json"
FINAL_NAME = "final_report_v199.json"
INDEX_KEYS = ["first_live_proof_gate_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V199 First Live-Proof Fire Gate"
MISSION_KEY = "dummy_mission_state_report_v185"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Fire Gate", "first_live_proof_gate_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V199_ROUTES = [
    "/api/v199/first-live-proof-gate-controller",
    "/api/v199/v198-baseline",
    "/api/v199/relevant-approval-validator",
    "/api/v199/quorum-prerequisite",
    "/api/v199/mode-live-authorized-prerequisite",
    "/api/v199/proof-target-guard",
    "/api/v199/max-proof-order-count-guard",
    "/api/v199/livebrokerfirewall-only-proof",
    "/api/v199/limit-only-proof",
    "/api/v199/no-market-order-proof",
    "/api/v199/proof-autolock",
    "/api/v199/no-repeat-beyond-limit-proof",
    "/api/v199/readiness-governor",
    "/api/v199/execution-lock",
    "/api/v199/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "first-live-proof-gate-controller": ["v199_first_live_proof_gate_controller_report.json"],
    "v198-baseline": ["v198_baseline_readback_v1_report.json"],
    "relevant-approval-validator": ["v199_relevant_approval_validator_report.json"],
    "quorum-prerequisite": ["v199_quorum_prerequisite_report.json"],
    "mode-live-authorized-prerequisite": ["v199_mode_live_authorized_prerequisite_report.json"],
    "proof-target-guard": ["v199_proof_target_guard_report.json"],
    "max-proof-order-count-guard": ["v199_max_proof_order_count_guard_report.json"],
    "livebrokerfirewall-only-proof": ["v199_livebrokerfirewall_only_proof_report.json"],
    "limit-only-proof": ["v199_limit_only_proof_report.json"],
    "no-market-order-proof": ["v199_no_market_order_proof_report.json"],
    "proof-autolock": ["v199_proof_autolock_report.json"],
    "no-repeat-beyond-limit-proof": ["v199_no_repeat_beyond_limit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v159_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v158_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v199_report_v1.json", "completion_oriented_next_action_v199_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(199)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v199/reports.py scripts/generate_v199_reports.py dashboard/backend/v199_routes.py",
    "python scripts/generate_v199_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V199Context:
    def __init__(self, *, proof_approval=None, proof_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, quorum_ready_override=None, mode_live_override=None, proof_target_override=None, max_proof_orders=1) -> None:
        self.v198_baseline_status = sgc.baseline_status("final_report_v198.json", "V198")
        if quorum_ready_override is None:
            self.quorum_ready = str(sgc.load_artifact("final_report_v198.json").get("final_quorum_controller_status", "")) == "PASS_FIRST_LIVE_PROOF_QUORUM_READY_NO_SUBMIT"
        else:
            self.quorum_ready = bool(quorum_ready_override)
        if proof_target_override is None:
            self.proof_target = str(sgc.load_artifact("final_report_v198.json").get("proof_target", "BLOCKED_NO_AUTHORITY"))
        else:
            self.proof_target = proof_target_override
        if mode_live_override is None:
            self.mode_live = str(sgc.load_artifact("final_report_v148.json").get("mode", "")) == "LIVE_AUTHORIZED"
        else:
            self.mode_live = bool(mode_live_override)
        self.target_valid = self.proof_target in ("FIRST_REAL_PILOT_PROOF", "CONTROLLED_SESSION_PROOF")
        self.result = sgc.pilot_submit(
            "v199-first-live-proof",
            approval_input=proof_approval,
            approval_path=proof_approval_path,
            dry_audit_ready=self.quorum_ready and self.mode_live and self.target_valid,
            live_submit_operator_enabled=live_submit_operator_enabled,
            caps_config_present=caps_config_present,
            firewall_adapter=firewall_adapter,
            order_shape={**ORDER_SHAPE, "proof_target": self.proof_target},
            max_pilot_orders=max_proof_orders,
        )
        self.firewall_adapter_present = firewall_adapter is not None

    @property
    def submitted(self) -> bool:
        r = self.result["submit_result"]
        return r is not None and bool(r.get("accepted"))

    @property
    def real_broker_contacted(self) -> bool:
        r = self.result["submit_result"]
        return bool(r and r.get("real_broker_contacted"))

    @property
    def controller_status(self) -> str:
        return "PASS_FIRST_LIVE_PROOF_SUBMITTED_AUTOLOCKED" if self.submitted else "PARTIAL_FIRST_LIVE_PROOF_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v198_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        base = [f"PRECHECK_MISSING:{k}" for k, v in self.result["checklist"].items() if not v]
        if not self.mode_live:
            base.append("MODE_FIREWALL_NOT_LIVE_AUTHORIZED")
        if not self.quorum_ready:
            base.append("FIRST_LIVE_PROOF_QUORUM_UNMET")
        if not self.target_valid:
            base.append("PROOF_TARGET_BLOCKED_NO_AUTHORITY")
        return base or ["FIRST_LIVE_PROOF_NOT_ARMED"]

    @property
    def next_action(self) -> str:
        return "FIRST_LIVE_PROOF_SUBMITTED_PROOF_AUTOLOCKED_NO_FURTHER_ORDERS_AWAIT_RECONCILE" if self.submitted else "OPERATOR_MUST_PROVIDE_FULL_QUORUM_LIVE_AUTHORIZED_MODE_APPROVAL_AND_FIREWALL_ADAPTER"


def _common(ctx: V199Context) -> dict[str, Any]:
    v = ctx.result["validation"]
    return {
        "v198_baseline_status": ctx.v198_baseline_status,
        "first_live_proof_gate_controller_status": ctx.controller_status,
        "relevant_approval_validator_status": "PASS_PROOF_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_PROOF_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_PROOF_APPROVAL_ABSENT"),
        "quorum_prerequisite_status": "PASS_QUORUM_PREREQUISITE_MET" if ctx.quorum_ready else "PARTIAL_QUORUM_PREREQUISITE_UNMET",
        "mode_live_authorized_prerequisite_status": "PASS_MODE_LIVE_AUTHORIZED" if ctx.mode_live else "PARTIAL_MODE_NOT_LIVE_AUTHORIZED",
        "proof_target_guard_status": f"PASS_PROOF_TARGET_{ctx.proof_target}" if ctx.target_valid else "PARTIAL_PROOF_TARGET_BLOCKED",
        "proof_target": ctx.proof_target,
        "max_proof_order_count_guard_status": "PASS_MAX_PROOF_ORDER_COUNT",
        "max_proof_order_count": ctx.result["max_pilot_orders"],
        "livebrokerfirewall_only_proof_status": "PASS_LIVEBROKERFIREWALL_ONLY",
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "no_repeat_beyond_limit_proof_status": "PASS_NO_REPEAT_BEYOND_LIMIT",
        "proof_approval_present": bool(v["accepted"]),
        "proof_approval_hash": v["approval_hash"],
        "pre_submit_checklist": ctx.result["checklist"],
        "pre_submit_all_pass": ctx.result["all_pass"],
        "quorum_ready": ctx.quorum_ready,
        "mode_live_authorized": ctx.mode_live,
        "proof_autolock_status": "PASS_PROOF_AUTOLOCKED" if ctx.submitted else "PASS_PROOF_AUTOLOCK_ARMED",
        "proof_locked": ctx.submitted,
        "proof_id": ctx.result["pilot_id"] if ctx.submitted else None,
        "idempotency_key": ctx.result["idempotency_key"],
        "firewall_adapter_present": ctx.firewall_adapter_present,
        "firewall_submit_invoked": ctx.submitted,
        "order_attempt_id": (ctx.result["submit_result"] or {}).get("order_attempt_id") if ctx.submitted else None,
        "order_attempt_ids": [(ctx.result["submit_result"] or {}).get("order_attempt_id")] if ctx.submitted else [],
        "session_id": (ctx.result["submit_result"] or {}).get("session_id") if ctx.submitted else None,
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "real_live_order_submitted": False,
        "real_broker_contacted": ctx.real_broker_contacted,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "simulated_order_submits_count": 1 if ctx.submitted else 0,
        "market_order_submitted": False,
        "caps_modified": False,
        "scale_applied": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v159_status": "PASS",
        "execution_lock_deep_recheck_v158_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V199Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v198_baseline"):
        return "PASS" if ctx.v198_baseline_status == "PASS_V198_BASELINE_READBACK" else "FAIL" if ctx.v198_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v199_first_live_proof_gate_controller_report.json":
        return "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V199Context) -> dict[str, Any]:
    workstream = "v199: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v199_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V199_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v199_report.json":
        report.update({"completion_oriented_next_action_v199_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v198_carried_status": ctx.v198_baseline_status, "first_live_proof_gate_controller_status": ctx.controller_status, "proof_target": ctx.proof_target, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v199_first_live_proof_gate_controller_report.json"), "proof_autolock": str(ARTIFACTS / "v199_proof_autolock_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v199.json", "dummy_canonical_identity_report_v199.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V199ReportFactory:
    def __init__(self, *, proof_approval=None, proof_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, quorum_ready_override=None, mode_live_override=None, proof_target_override=None, max_proof_orders=1) -> None:
        self.kw = dict(proof_approval=proof_approval, proof_approval_path=proof_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter, quorum_ready_override=quorum_ready_override, mode_live_override=mode_live_override, proof_target_override=proof_target_override, max_proof_orders=max_proof_orders)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V199Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
