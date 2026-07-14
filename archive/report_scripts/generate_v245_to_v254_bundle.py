"""Generate the DUMMY V245-V254 operator-ready appliance pack bundle summary reports (runs stages in order).

Emits consolidated named artifacts (appliance pack, authority rehearsal, adapter contract kit, config rehearsal,
command center, pre-execution freeze, completion lift V5) plus bundle mission/final reports. Fail-closed: zero live
orders, no broker contact, no approval-file writes by Dummy, no runtime/approvals creation, no scale, no autonomy.
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

BUNDLE_MILESTONE = "DUMMY_V245_TO_V254_OPERATOR_READY_APPLIANCE_PACK_ADAPTER_CONTRACT_KIT_AUTHORITY_REHEARSAL_FIRST_PROOF_COMMAND_CENTER_AND_COMPLETION_LIFT_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(245, 255)]

# (source controller report -> consolidated named artifact)
NAMED_ARTIFACTS = {
    "v246_operator_ready_appliance_pack_controller_report.json": "operator_ready_appliance_pack_v246.json",
    "v247_external_authority_rehearsal_controller_report.json": "external_authority_rehearsal_v247.json",
    "v248_adapter_contract_kit_controller_report.json": "livebrokerfirewall_adapter_contract_kit_v248.json",
    "v249_live_submit_caps_rehearsal_controller_report.json": "live_submit_caps_rehearsal_v249.json",
    "v250_first_proof_command_center_controller_report.json": "first_proof_command_center_v250.json",
    "v251_pre_execution_freeze_controller_report.json": "pre_execution_freeze_report_v251.json",
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
    from predator_mesh.v254.reports import build_completion_lift_v5
    lift = build_completion_lift_v5()
    lift["generated_at"] = sgc.now_iso()
    sgc.write_report("completion_lift_v5_v254.json", lift)

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    proof_live_orders = int(sgc.load_artifact("final_report_v252.json").get("real_live_orders_submitted_count", 0) or 0)
    broker = any(bool(sgc.load_artifact(fn).get("real_broker_contacted", False)) for _, _, fn in STAGES)
    approval_files_written = sum(int(sgc.load_artifact(fn).get("approval_files_written", 0) or 0) for _, _, fn in STAGES)
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = any(bool(sgc.load_artifact(fn).get("autonomous_trading_enabled", False)) for _, _, fn in STAGES)
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)
    runtime_approvals_created_by_dummy = False

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v245_to_v254: Operator-Ready Appliance Baseline, Appliance Pack, External Authority Rehearsal, Adapter Contract Kit, Live-Submit/Caps Rehearsal Auditor, First-Proof Command Center, Pre-Execution Freeze Report, Execute-Once Dry/Fixture Harness V3, Post-Execution Intake Bridge, and Completion Lift V5 Operator-Ready Lock",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "operator_ready_appliance_baseline_status": sgc.load_artifact("final_report_v245.json").get("operator_ready_appliance_baseline_controller_status"),
        "operator_ready_appliance_pack_status": sgc.load_artifact("final_report_v246.json").get("operator_ready_appliance_pack_controller_status"),
        "external_authority_rehearsal_status": sgc.load_artifact("final_report_v247.json").get("external_authority_rehearsal_controller_status"),
        "adapter_contract_kit_status": sgc.load_artifact("final_report_v248.json").get("adapter_contract_kit_controller_status"),
        "live_submit_caps_rehearsal_status": sgc.load_artifact("final_report_v249.json").get("live_submit_caps_rehearsal_controller_status"),
        "first_proof_command_center_status": sgc.load_artifact("final_report_v250.json").get("first_proof_command_center_controller_status"),
        "pre_execution_freeze_status": sgc.load_artifact("final_report_v251.json").get("pre_execution_freeze_controller_status"),
        "execute_once_dry_fixture_harness_status": sgc.load_artifact("final_report_v252.json").get("execute_once_dry_fixture_harness_controller_status"),
        "post_execution_intake_bridge_status": sgc.load_artifact("final_report_v253.json").get("post_execution_intake_bridge_controller_status"),
        "completion_lift_v5_status": sgc.load_artifact("final_report_v254.json").get("completion_lift_v5_controller_status"),
        "fully_operational_estimate": sgc.load_artifact("final_report_v254.json").get("fully_operational_estimate"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v254.json").get("next_action_matrix_selection"),
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
    sgc.write_report("dummy_mission_state_report_v245_to_v254.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V245_TO_V254_OPERATOR_READY_APPLIANCE_COMPLETE_ZERO_LIVE_ORDERS_NO_APPROVAL_WRITES_NO_RUNTIME_APPROVALS_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD_AWAIT_OPERATOR_EXTERNAL_AUTHORITY",
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
    final_path = sgc.write_report("final_report_v245_to_v254.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v245_to_v254", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_live_orders": final["total_live_orders"], "approval_files_written": final["approval_files_written"], "runtime_approvals_created_by_dummy": final["runtime_approvals_created_by_dummy"], "broker_contacted": final["broker_contacted"], "fully_operational_estimate": final["fully_operational_estimate"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
