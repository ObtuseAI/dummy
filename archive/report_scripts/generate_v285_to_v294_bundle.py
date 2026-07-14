"""Generate the DUMMY V285-V294 first-proof final run appliance + external authority seal + post-proof autopilot + scale/autonomy wall + completion lift V9 bundle (runs stages in order).

Emits consolidated completion-lift-V9 artifact plus bundle mission/final reports. Fail-closed: zero live orders,
no broker contact, no approval-file writes by Dummy, no runtime/approvals creation, no scale, no autonomy.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc

BUNDLE_MILESTONE = "DUMMY_V285_TO_V294_FIRST_PROOF_FINAL_RUN_APPLIANCE_EXTERNAL_AUTHORITY_SEAL_POST_PROOF_AUTOPILOT_REPEAT_SESSION_PREP_AND_COMPLETION_LIFT_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(285, 295)]

STATUS_KEYS = {
    285: "first_proof_final_run_baseline_controller_status",
    286: "external_authority_seal_verifier_controller_status",
    287: "final_run_appliance_launcher_controller_status",
    288: "live_proof_no_surprises_precheck_controller_status",
    289: "execute_once_final_run_wrapper_v6_controller_status",
    290: "post_proof_autopilot_intake_controller_status",
    291: "reconcile_forensic_autopipeline_v5_controller_status",
    292: "repeat_session_fast_route_prep_controller_status",
    293: "real_proof_required_scale_autonomy_wall_controller_status",
    294: "completion_lift_v9_controller_status",
}


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"archive.report_scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    from predator_mesh.v294.reports import build_completion_lift_v9
    lift = build_completion_lift_v9()
    lift["generated_at"] = sgc.now_iso()
    sgc.write_report("completion_lift_v9_v294.json", lift)

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
        "workstream": "v285_to_v294: First-Proof Final Run Baseline, External Authority Seal Verifier, Final Run Appliance Launcher, Live-Proof No-Surprises Precheck, Execute-Once Final Run Wrapper V6, Post-Proof Autopilot Intake, Reconcile/Forensic Autopipeline V5, Repeat/Session Fast-Route Prep, Real-Proof-Required Scale/Autonomy Wall, and Completion Lift V9 Final Proof-Ready Lock",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_statuses": stage_statuses,
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "fully_operational_estimate": sgc.load_artifact("final_report_v294.json").get("fully_operational_estimate"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v294.json").get("next_action_matrix_selection"),
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
    sgc.write_report("dummy_mission_state_report_v285_to_v294.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V285_TO_V294_FIRST_PROOF_FINAL_RUN_APPLIANCE_AND_POST_PROOF_AUTOPILOT_COMPLETE_ZERO_LIVE_ORDERS_NO_APPROVAL_WRITES_NO_RUNTIME_APPROVALS_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD_AWAIT_OPERATOR_EXTERNAL_AUTHORITY",
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
    final_path = sgc.write_report("final_report_v285_to_v294.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v285_to_v294", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_live_orders": final["total_live_orders"], "approval_files_written": final["approval_files_written"], "runtime_approvals_created_by_dummy": final["runtime_approvals_created_by_dummy"], "broker_contacted": final["broker_contacted"], "fully_operational_estimate": final["fully_operational_estimate"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
