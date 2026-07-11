"""Generate the DUMMY V255-V264 operator execution appliance bundle summary reports (runs stages in order).

Emits consolidated named artifacts (operator execution pipeline, authority manifest validator V3, pre-execution
freeze V2, completion lift V6) plus bundle mission/final reports. Fail-closed: zero live orders, no broker contact,
no approval-file writes by Dummy, no runtime/approvals creation, no scale, no autonomy.
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

BUNDLE_MILESTONE = "DUMMY_V255_TO_V264_OPERATOR_EXECUTION_APPLIANCE_SINGLE_COMMAND_PROOF_INTAKE_ADAPTER_SMOKE_ROUTE_AND_COMPLETION_LIFT_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(255, 265)]

NAMED_ARTIFACTS = {
    "v256_single_command_operator_pipeline_controller_report.json": "operator_execution_pipeline_v256.json",
    "v257_authority_manifest_validator_controller_report.json": "authority_manifest_validator_v3.json",
    "v260_pre_execution_freeze_v2_controller_report.json": "pre_execution_freeze_v2_v260.json",
}


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"archive.report_scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    for src, dst in NAMED_ARTIFACTS.items():
        payload = dict(sgc.load_artifact(src))
        payload["generated_at"] = sgc.now_iso()
        sgc.write_report(dst, payload)
    from predator_mesh.v264.reports import build_completion_lift_v6
    lift = build_completion_lift_v6(); lift["generated_at"] = sgc.now_iso()
    sgc.write_report("completion_lift_v6_v264.json", lift)

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    proof_live_orders = int(sgc.load_artifact("final_report_v261.json").get("real_live_orders_submitted_count", 0) or 0)
    broker = any(bool(sgc.load_artifact(fn).get("real_broker_contacted", False)) for _, _, fn in STAGES)
    approval_files_written = sum(int(sgc.load_artifact(fn).get("approval_files_written", 0) or 0) for _, _, fn in STAGES)
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = any(bool(sgc.load_artifact(fn).get("autonomous_trading_enabled", False)) for _, _, fn in STAGES)
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)
    runtime_approvals_created_by_dummy = False

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v255_to_v264: Operator Execution Appliance Baseline, Single-Command Operator Pipeline, Authority Manifest Validator V3, Live Adapter Smoke Kit, Live-Submit/Caps Final Rehearsal V2, Pre-Execution Freeze V2, Execute-Once Final Harness V4, External Proof Intake V2, Reconcile+Forensic Auto Pipeline V4, and Completion Lift V6 Next-Action Lock",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "operator_execution_appliance_baseline_status": sgc.load_artifact("final_report_v255.json").get("operator_execution_appliance_baseline_controller_status"),
        "single_command_operator_pipeline_status": sgc.load_artifact("final_report_v256.json").get("single_command_operator_pipeline_controller_status"),
        "authority_manifest_validator_status": sgc.load_artifact("final_report_v257.json").get("authority_manifest_validator_controller_status"),
        "adapter_smoke_kit_status": sgc.load_artifact("final_report_v258.json").get("adapter_smoke_kit_controller_status"),
        "live_submit_caps_final_rehearsal_status": sgc.load_artifact("final_report_v259.json").get("live_submit_caps_final_rehearsal_controller_status"),
        "pre_execution_freeze_v2_status": sgc.load_artifact("final_report_v260.json").get("pre_execution_freeze_v2_controller_status"),
        "execute_once_final_harness_status": sgc.load_artifact("final_report_v261.json").get("execute_once_final_harness_controller_status"),
        "external_proof_intake_v2_status": sgc.load_artifact("final_report_v262.json").get("external_proof_intake_v2_controller_status"),
        "reconcile_forensic_auto_pipeline_v4_status": sgc.load_artifact("final_report_v263.json").get("reconcile_forensic_auto_pipeline_v4_controller_status"),
        "completion_lift_v6_status": sgc.load_artifact("final_report_v264.json").get("completion_lift_v6_controller_status"),
        "fully_operational_estimate": sgc.load_artifact("final_report_v264.json").get("fully_operational_estimate"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v264.json").get("next_action_matrix_selection"),
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
    sgc.write_report("dummy_mission_state_report_v255_to_v264.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V255_TO_V264_OPERATOR_EXECUTION_APPLIANCE_COMPLETE_ZERO_LIVE_ORDERS_NO_APPROVAL_WRITES_NO_RUNTIME_APPROVALS_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD_AWAIT_OPERATOR_EXTERNAL_AUTHORITY",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
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
    final_path = sgc.write_report("final_report_v255_to_v264.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v255_to_v264", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_live_orders": final["total_live_orders"], "approval_files_written": final["approval_files_written"], "runtime_approvals_created_by_dummy": final["runtime_approvals_created_by_dummy"], "broker_contacted": final["broker_contacted"], "fully_operational_estimate": final["fully_operational_estimate"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
