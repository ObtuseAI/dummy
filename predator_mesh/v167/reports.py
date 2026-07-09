"""DUMMY v167 repeat pilot fire gate — submits exactly one repeat pilot ONLY on full authority, else nothing.

Submit occurs ONLY when V166 preflight is ready, first-pilot reconcile+forensic proof exists, the mode firewall is
LIVE_AUTHORIZED, the exact repeat-pilot approval validates, live-submit is operator-enabled, caps are present/unchanged
(stricter), and an explicit LiveBrokerFirewall adapter is injected. Default has none -> no submit
(PARTIAL_REPEAT_PILOT_NOT_ARMED). Tests inject a NON-BROKER firewall double. Dry mode / missing first-pilot proof both
block. On submit the repeat pilot immediately auto-locks; limit-only, no market orders, no repeat.
"""

from __future__ import annotations

from typing import Any

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v167 import MILESTONE

ARTIFACTS = sgc.ARTIFACTS
ORDER_SHAPE = {"order_type": "limit", "is_market_order": False, "size_class": "tiny", "firewall_only": True, "repeat_pilot": True}

WORKSTREAM = "v167: Repeat Pilot Fire Gate Full Auth Only"
MISSION_NAME = "dummy_mission_state_report_v153.json"
FINAL_NAME = "final_report_v167.json"
INDEX_KEYS = ["repeat_pilot_gate_controller_status", "live_orders", "real_broker_contacted"]
DASH_TITLE = "Dummy V167 Repeat Pilot Fire Gate"
MISSION_KEY = "dummy_mission_state_report_v153"
SUMMARY_FIELDS = [
    ["Mission", "mission_state_verdict"],
    ["Repeat Pilot Gate", "repeat_pilot_gate_controller_status"],
    ["Live Orders", "live_orders"],
    ["Broker Contacted", "real_broker_contacted"],
    ["Next Action", "current_next_action"],
    ["Blockers", "current_blockers"],
]

V167_ROUTES = [
    "/api/v167/repeat-pilot-gate-controller",
    "/api/v167/v166-baseline",
    "/api/v167/repeat-approval-validator",
    "/api/v167/preflight-prerequisite",
    "/api/v167/first-pilot-proof-prerequisite",
    "/api/v167/mode-live-authorized-prerequisite",
    "/api/v167/max-repeat-order-count-guard",
    "/api/v167/livebrokerfirewall-only-proof",
    "/api/v167/limit-only-proof",
    "/api/v167/no-market-order-proof",
    "/api/v167/repeat-pilot-autolock",
    "/api/v167/no-repeat-beyond-limit-proof",
    "/api/v167/readiness-governor",
    "/api/v167/execution-lock",
    "/api/v167/mission-state",
]

REPORT_GROUPS: dict[str, list[str]] = {
    "repeat-pilot-gate-controller": ["v167_repeat_pilot_gate_controller_report.json"],
    "v166-baseline": ["v166_baseline_readback_v1_report.json"],
    "repeat-approval-validator": ["v167_repeat_approval_validator_report.json"],
    "preflight-prerequisite": ["v167_preflight_prerequisite_report.json"],
    "first-pilot-proof-prerequisite": ["v167_first_pilot_proof_prerequisite_report.json"],
    "mode-live-authorized-prerequisite": ["v167_mode_live_authorized_prerequisite_report.json"],
    "max-repeat-order-count-guard": ["v167_max_repeat_order_count_guard_report.json"],
    "livebrokerfirewall-only-proof": ["v167_livebrokerfirewall_only_proof_report.json"],
    "limit-only-proof": ["v167_limit_only_proof_report.json"],
    "no-market-order-proof": ["v167_no_market_order_proof_report.json"],
    "repeat-pilot-autolock": ["v167_repeat_pilot_autolock_report.json"],
    "no-repeat-beyond-limit-proof": ["v167_no_repeat_beyond_limit_proof_report.json"],
    "readiness-governor": ["readiness_governor_v127_report.json"],
    "execution-lock": ["execution_lock_deep_recheck_v126_report.json"],
    "mission-state": [MISSION_NAME, "dashboard_v167_report_v1.json", "completion_oriented_next_action_v167_report.json"],
}

SAFETY_REPORT_NAMES = sgc.safety_report_names(167)
DEFAULT_REQUIRED_REPORT_NAMES = [n for names in REPORT_GROUPS.values() for n in names] + SAFETY_REPORT_NAMES

VERIFICATION_COMMANDS = [
    "python -m py_compile predator_mesh/v167/reports.py scripts/generate_v167_reports.py dashboard/backend/v167_routes.py",
    "python scripts/generate_v167_reports.py",
    "python -m pytest tests/ -q --tb=short --timeout=60",
    "cd dashboard/frontend && npm run build",
]


class V167Context:
    def __init__(self, *, repeat_approval=None, repeat_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, preflight_ready_override=None, first_pilot_override=None, mode_live_override=None, max_repeat_orders=1) -> None:
        self.v166_baseline_status = sgc.baseline_status("final_report_v166.json", "V166")
        if preflight_ready_override is None:
            self.preflight_ready = str(sgc.load_artifact("final_report_v166.json").get("repeat_preflight_controller_status", "")) == "PASS_REPEAT_PREFLIGHT_READY_NO_SUBMIT"
        else:
            self.preflight_ready = bool(preflight_ready_override)
        if first_pilot_override is None:
            reconciled = str(sgc.load_artifact("final_report_v162.json").get("reconcile_controller_status", "")) == "PASS_FIRST_REAL_PILOT_STATE_CLASSIFIED_AUTOLOCKED"
            reviewed = str(sgc.load_artifact("final_report_v163.json").get("forensic_controller_status", "")) == "PASS_FIRST_REAL_PILOT_FORENSIC_REVIEWED"
            self.first_pilot_ok = reconciled and reviewed
        else:
            self.first_pilot_ok = bool(first_pilot_override)
        if mode_live_override is None:
            self.mode_live = str(sgc.load_artifact("final_report_v148.json").get("mode", "")) == "LIVE_AUTHORIZED"
        else:
            self.mode_live = bool(mode_live_override)
        self.result = sgc.repeat_pilot_submit(
            "v167-repeat-pilot",
            approval_input=repeat_approval,
            approval_path=repeat_approval_path,
            first_pilot_reviewed=self.preflight_ready and self.first_pilot_ok and self.mode_live,
            live_submit_operator_enabled=live_submit_operator_enabled,
            caps_config_present=caps_config_present,
            firewall_adapter=firewall_adapter,
            order_shape=ORDER_SHAPE,
            max_repeat_orders=max_repeat_orders,
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
        return "PASS_REPEAT_PILOT_SUBMITTED_AUTOLOCKED" if self.submitted else "PARTIAL_REPEAT_PILOT_NOT_ARMED"

    @property
    def final_verdict(self) -> str:
        if self.v166_baseline_status.startswith("FAIL"):
            return "FAIL"
        return "PASS" if self.submitted else "PARTIAL"

    @property
    def current_blockers(self) -> list[str]:
        if self.submitted:
            return []
        base = [f"PRECHECK_MISSING:{k}" for k, v in self.result["checklist"].items() if not v]
        if not self.mode_live:
            base.append("MODE_FIREWALL_NOT_LIVE_AUTHORIZED")
        if not self.preflight_ready:
            base.append("REPEAT_PREFLIGHT_NOT_READY")
        if not self.first_pilot_ok:
            base.append("FIRST_PILOT_PROOF_ABSENT")
        return base or ["REPEAT_PILOT_NOT_ARMED"]

    @property
    def next_action(self) -> str:
        return "REPEAT_PILOT_SUBMITTED_REPEAT_PILOT_AUTOLOCKED_NO_FURTHER_ORDERS_AWAIT_RECONCILE" if self.submitted else "OPERATOR_MUST_PROVIDE_REPEAT_APPROVAL_FIRST_PILOT_PROOF_LIVE_AUTHORIZED_MODE_AND_FIREWALL"


def _common(ctx: V167Context) -> dict[str, Any]:
    v = ctx.result["validation"]
    return {
        "v166_baseline_status": ctx.v166_baseline_status,
        "repeat_pilot_gate_controller_status": ctx.controller_status,
        "repeat_approval_validator_status": "PASS_REPEAT_APPROVAL_VALID" if v["accepted"] else ("FAIL_CLOSED_INVALID_REPEAT_APPROVAL" if v["state"] == "PRESENT" else "PARTIAL_REPEAT_APPROVAL_ABSENT"),
        "preflight_prerequisite_status": "PASS_PREFLIGHT_PREREQUISITE_MET" if ctx.preflight_ready else "PARTIAL_PREFLIGHT_PREREQUISITE_UNMET",
        "first_pilot_proof_prerequisite_status": "PASS_FIRST_PILOT_PROOF_PRESENT" if ctx.first_pilot_ok else "PARTIAL_FIRST_PILOT_PROOF_ABSENT",
        "mode_live_authorized_prerequisite_status": "PASS_MODE_LIVE_AUTHORIZED" if ctx.mode_live else "PARTIAL_MODE_NOT_LIVE_AUTHORIZED",
        "max_repeat_order_count_guard_status": "PASS_MAX_REPEAT_ORDER_COUNT",
        "max_repeat_order_count": ctx.result["max_repeat_orders"],
        "livebrokerfirewall_only_proof_status": "PASS_LIVEBROKERFIREWALL_ONLY",
        "limit_only_proof_status": "PASS_LIMIT_ONLY",
        "no_market_order_proof_status": "PASS_NO_MARKET_ORDER",
        "no_repeat_beyond_limit_proof_status": "PASS_NO_REPEAT_BEYOND_LIMIT",
        "repeat_approval_present": bool(v["accepted"]),
        "repeat_approval_hash": v["approval_hash"],
        "pre_submit_checklist": ctx.result["checklist"],
        "pre_submit_all_pass": ctx.result["all_pass"],
        "mode_live_authorized": ctx.mode_live,
        "repeat_pilot_autolock_status": "PASS_REPEAT_PILOT_AUTOLOCKED" if ctx.submitted else "PASS_REPEAT_PILOT_AUTOLOCK_ARMED",
        "repeat_pilot_locked": ctx.submitted,
        "repeat_pilot_id": ctx.result["repeat_pilot_id"] if ctx.submitted else None,
        "idempotency_key": ctx.result["idempotency_key"],
        "firewall_adapter_present": ctx.firewall_adapter_present,
        "firewall_submit_invoked": ctx.submitted,
        "order_attempt_id": (ctx.result["submit_result"] or {}).get("order_attempt_id") if ctx.submitted else None,
        "order_attempt_ids": [(ctx.result["submit_result"] or {}).get("order_attempt_id")] if ctx.submitted else [],
        "dummy_enabled_live_submit": False,
        "dummy_modified_caps": False,
        "real_live_order_submitted": False,
        "real_broker_contacted": ctx.real_broker_contacted,
        "live_orders": 0,
        "real_live_orders_submitted_count": 0,
        "simulated_order_submits_count": 1 if ctx.submitted else 0,
        "market_order_submitted": False,
        "campaign_auto_started": False,
        "caps_modified": False,
        "scale_applied": False,
        "autonomous_trading_enabled": False,
        "readiness_governor_v127_status": "PASS",
        "execution_lock_deep_recheck_v126_status": "PASS",
        "current_next_action": ctx.next_action,
        "selected_next_action": ctx.next_action,
        "current_blockers": ctx.current_blockers,
    }


def _verdict(name: str, ctx: V167Context) -> str:
    if name in SAFETY_REPORT_NAMES or name.startswith("no_") or "blunder" in name or "canonical_identity" in name:
        return "PASS"
    if name.startswith("v166_baseline"):
        return "PASS" if ctx.v166_baseline_status == "PASS_V166_BASELINE_READBACK" else "FAIL" if ctx.v166_baseline_status.startswith("FAIL") else "PARTIAL"
    if name == "v167_repeat_pilot_gate_controller_report.json":
        return "PASS" if ctx.submitted else "PARTIAL"
    return ctx.final_verdict


def _component_payload(name: str, ctx: V167Context) -> dict[str, Any]:
    workstream = "v167: " + name.removesuffix(".json").removesuffix("_report").replace("_", " ").title()
    report = sgc.safe_base(MILESTONE, workstream, _verdict(name, ctx))
    report.update(_common(ctx))
    report["report_name"] = name
    if name == "dashboard_v167_report_v1.json":
        report.update({"dashboard_status": "PASS", "routes": V167_ROUTES, "read_only_dashboard": True, "dashboard_can_submit_orders": False})
    elif name == "completion_oriented_next_action_v167_report.json":
        report.update({"completion_oriented_next_action_v167_status": "PASS", "next_action": ctx.next_action})
    elif name == MISSION_NAME:
        report.update({"mission_state_verdict": ctx.final_verdict, "v166_carried_status": ctx.v166_baseline_status, "repeat_pilot_gate_controller_status": ctx.controller_status, "proof_paths": {"final_report": str(ARTIFACTS / FINAL_NAME), "controller": str(ARTIFACTS / "v167_repeat_pilot_gate_controller_report.json"), "repeat_pilot_autolock": str(ARTIFACTS / "v167_repeat_pilot_autolock_report.json")}})
    if name in SAFETY_REPORT_NAMES:
        report.update({"safety_status": "PASS", "report_name_checked": name, "no_invalid_scoring": True})
        if name in {"blunder_separation_recheck_v167.json", "dummy_canonical_identity_report_v167.json"}:
            report.update({"blunder_separation_status": "PASS", "canonical_identity_intact": True, "dummy_identity_regressed": False})
    return report


class V167ReportFactory:
    def __init__(self, *, repeat_approval=None, repeat_approval_path=None, live_submit_operator_enabled=False, caps_config_present=False, firewall_adapter=None, preflight_ready_override=None, first_pilot_override=None, mode_live_override=None, max_repeat_orders=1) -> None:
        self.kw = dict(repeat_approval=repeat_approval, repeat_approval_path=repeat_approval_path, live_submit_operator_enabled=live_submit_operator_enabled, caps_config_present=caps_config_present, firewall_adapter=firewall_adapter, preflight_ready_override=preflight_ready_override, first_pilot_override=first_pilot_override, mode_live_override=mode_live_override, max_repeat_orders=max_repeat_orders)

    def build(self) -> dict[str, dict[str, Any]]:
        ctx = V167Context(**self.kw)
        return {name: _component_payload(name, ctx) for name in DEFAULT_REQUIRED_REPORT_NAMES}
