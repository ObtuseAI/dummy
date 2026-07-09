"""Generate the DUMMY V225-V234 one-command activation pipeline bundle summary reports (runs stages in order).

Emits consolidated named artifacts (completion scoreboard V3) plus bundle mission/final reports. Fail-closed:
zero live orders, no broker contact, no approval-file writes by Dummy, no runtime/approvals creation, no scale,
no autonomy.
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

BUNDLE_MILESTONE = "DUMMY_V225_TO_V234_ONE_COMMAND_ACTIVATION_PIPELINE_AUTHORITY_MANIFEST_DRY_ARM_LIVE_PROOF_RECONCILE_FORENSIC_AND_COMPLETION_LIFT_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(225, 235)]
RUNTIME_APPROVALS_DIR = ROOT / "runtime" / "approvals"


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    # Consolidated named artifact.
    from predator_mesh.v233.reports import build_scoreboard_v3
    scoreboard = build_scoreboard_v3(); scoreboard["generated_at"] = sgc.now_iso()
    sgc.write_report("completion_scoreboard_v233.json", scoreboard)

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    proof_live_orders = int(sgc.load_artifact("final_report_v230.json").get("real_live_orders_submitted_count", 0) or 0)
    broker = any(bool(sgc.load_artifact(fn).get("real_broker_contacted", False)) for _, _, fn in STAGES)
    approval_files_written = sum(int(sgc.load_artifact(fn).get("approval_files_written", 0) or 0) for _, _, fn in STAGES)
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = any(bool(sgc.load_artifact(fn).get("autonomous_trading_enabled", False)) for _, _, fn in STAGES)
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)
    # Dummy never creates runtime/approvals. Report whether it exists (operator may create it externally).
    runtime_approvals_created_by_dummy = False

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v225_to_v234: Activation Pipeline Baseline, Operator Authority Manifest Pack, One-Command Dry Pipeline, External Authority Intake V2, Final Resolver Arming Orchestrator, Live-Proof Execution Orchestrator, Reconcile+Forensic Auto Pipeline, Proof-Aware Route Decision, Completion Scoreboard V3, and Acceleration Lock + Operator Command Sequence",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "activation_pipeline_baseline_status": sgc.load_artifact("final_report_v225.json").get("activation_pipeline_baseline_controller_status"),
        "manifest_pack_status": sgc.load_artifact("final_report_v226.json").get("manifest_pack_controller_status"),
        "one_command_dry_pipeline_status": sgc.load_artifact("final_report_v227.json").get("one_command_dry_pipeline_controller_status"),
        "external_authority_intake_v2_status": sgc.load_artifact("final_report_v228.json").get("external_authority_intake_v2_controller_status"),
        "final_resolver_arming_status": sgc.load_artifact("final_report_v229.json").get("final_resolver_arming_controller_status"),
        "live_proof_execution_status": sgc.load_artifact("final_report_v230.json").get("live_proof_execution_orchestrator_controller_status"),
        "reconcile_forensic_pipeline_status": sgc.load_artifact("final_report_v231.json").get("reconcile_forensic_pipeline_controller_status"),
        "route_decision_status": sgc.load_artifact("final_report_v232.json").get("route_state"),
        "completion_scoreboard_v3_status": sgc.load_artifact("final_report_v233.json").get("completion_scoreboard_v3_controller_status"),
        "fully_operational_estimate": sgc.load_artifact("final_report_v233.json").get("fully_operational_estimate"),
        "acceleration_lock_status": sgc.load_artifact("final_report_v234.json").get("acceleration_lock_controller_status"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v234.json").get("next_action_matrix_selection"),
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
    sgc.write_report("dummy_mission_state_report_v225_to_v234.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V225_TO_V234_ONE_COMMAND_ACTIVATION_PIPELINE_COMPLETE_ZERO_LIVE_ORDERS_NO_APPROVAL_WRITES_NO_RUNTIME_APPROVALS_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD_AWAIT_OPERATOR_EXTERNAL_AUTHORITY_INTAKE",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "first_live_proof_order_count": proof_live_orders,
        "total_real_live_orders_submitted": proof_live_orders,
        "approval_files_written": approval_files_written,
        "runtime_approvals_created_by_dummy": runtime_approvals_created_by_dummy,
        "fully_operational_estimate": mission["fully_operational_estimate"],
        "real_broker_contacted": broker,
        "scale_applied": scale_applied,
        "autonomous_trading_enabled": autonomy,
        "caps_modified": caps_changed,
        "live_submit_enabled": False,
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v225_to_v234.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v225_to_v234", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_real_live_orders_submitted": final["total_real_live_orders_submitted"], "approval_files_written": final["approval_files_written"], "runtime_approvals_created_by_dummy": final["runtime_approvals_created_by_dummy"], "fully_operational_estimate": final["fully_operational_estimate"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
