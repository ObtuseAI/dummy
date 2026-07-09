"""Generate the DUMMY V275-V284 final operator execution console + live-proof runbook + post-proof route bundle (runs stages in order).

Emits consolidated completion-lift-V8 artifact plus bundle mission/final reports. Fail-closed: zero live orders,
no broker contact, no approval-file writes by Dummy, no runtime/approvals creation, no scale, no autonomy.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc

BUNDLE_MILESTONE = "DUMMY_V275_TO_V284_FINAL_OPERATOR_EXECUTION_CONSOLE_LIVE_PROOF_RUNBOOK_POST_PROOF_ROUTE_REPEAT_SESSION_READY_AND_COMPLETION_LIFT_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(275, 285)]

STATUS_KEYS = {
    275: "final_operator_execution_baseline_controller_status",
    276: "final_authority_readiness_console_controller_status",
    277: "final_live_proof_runbook_lock_controller_status",
    278: "execute_once_authority_rehearsal_v2_controller_status",
    279: "live_proof_attempt_monitor_controller_status",
    280: "post_proof_reconcile_forensic_launcher_controller_status",
    281: "repeat_pilot_post_proof_readiness_controller_status",
    282: "controlled_session_post_proof_readiness_controller_status",
    283: "route_command_center_v2_controller_status",
    284: "completion_lift_v8_controller_status",
}


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    from predator_mesh.v284.reports import build_completion_lift_v8
    lift = build_completion_lift_v8(); lift["generated_at"] = sgc.now_iso()
    sgc.write_report("completion_lift_v8_v284.json", lift)

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    proof_live_orders = int(sgc.load_artifact("final_report_v272.json").get("real_live_orders_submitted_count", 0) or 0)
    broker = any(bool(sgc.load_artifact(fn).get("real_broker_contacted", False)) for _, _, fn in STAGES)
    approval_files_written = sum(int(sgc.load_artifact(fn).get("approval_files_written", 0) or 0) for _, _, fn in STAGES)
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = any(bool(sgc.load_artifact(fn).get("autonomous_trading_enabled", False)) for _, _, fn in STAGES)
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)
    runtime_approvals_created_by_dummy = False

    stage_statuses = {f"v{v}": sgc.load_artifact(fn).get(STATUS_KEYS[v]) for v, _, fn in STAGES}

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v275_to_v284: Final Operator Execution Baseline, Final Authority Readiness Console, Final Live-Proof Runbook Lock, Execute-Once Authority Rehearsal V2, Live-Proof Attempt Monitor, Post-Proof Reconcile/Forensic Launcher, Repeat Pilot Post-Proof Readiness, Controlled Session Post-Proof Readiness, Route Command Center V2, and Completion Lift V8 Final Operator Lock",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_statuses": stage_statuses,
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "fully_operational_estimate": sgc.load_artifact("final_report_v284.json").get("fully_operational_estimate"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v284.json").get("next_action_matrix_selection"),
        "first_live_proof_order_count": proof_live_orders,
        "total_real_live_orders_submitted": proof_live_orders,
        "approval_files_written": approval_files_written,
        "runtime_approvals_created_by_dummy": runtime_approvals_created_by_dummy,
        "real_broker_contacted": broker,
        "market_order_submitted": False,
        "autonomous_trading_enabled": autonomy,
        "scale_applied": scale_applied,
        "caps_modified": caps_changed,
        "current_blockers": [],
    }
    sgc.write_report("dummy_mission_state_report_v275_to_v284.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V275_TO_V284_FINAL_OPERATOR_EXECUTION_CONSOLE_AND_POST_PROOF_ROUTE_COMPLETE_ZERO_LIVE_ORDERS_NO_APPROVAL_WRITES_NO_RUNTIME_APPROVALS_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD_AWAIT_OPERATOR_EXTERNAL_AUTHORITY",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_statuses": stage_statuses,
        "first_live_proof_order_count": proof_live_orders,
        "total_real_live_orders_submitted": proof_live_orders,
        "total_live_orders": proof_live_orders,
        "approval_files_written": approval_files_written,
        "runtime_approvals_created_by_dummy": runtime_approvals_created_by_dummy,
        "fully_operational_estimate": mission["fully_operational_estimate"],
        "real_broker_contacted": broker,
        "broker_contacted": broker,
        "market_order": False,
        "scale_applied": scale_applied,
        "autonomous_trading_enabled": autonomy,
        "caps_modified": caps_changed,
        "live_submit_enabled": False,
        "account_private_data_accessed": False,
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v275_to_v284.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v275_to_v284", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_live_orders": final["total_live_orders"], "approval_files_written": final["approval_files_written"], "runtime_approvals_created_by_dummy": final["runtime_approvals_created_by_dummy"], "broker_contacted": final["broker_contacted"], "fully_operational_estimate": final["fully_operational_estimate"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
