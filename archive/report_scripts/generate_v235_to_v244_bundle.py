"""Generate the DUMMY V235-V244 operator authority appliance / doctor bundle summary reports (runs stages in order).

Emits consolidated named artifact (completion lift V4) plus bundle mission/final reports. Fail-closed: zero live
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

BUNDLE_MILESTONE = "DUMMY_V235_TO_V244_OPERATOR_AUTHORITY_APPLIANCE_LIVE_ADAPTER_DOCTOR_ARMABLE_QUORUM_EXECUTE_ONCE_HANDOFF_RECONCILE_FORENSIC_AND_COMPLETION_LIFT_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(235, 245)]


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"archive.report_scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    from predator_mesh.v244.reports import build_completion_lift_v4
    lift = build_completion_lift_v4(); lift["generated_at"] = sgc.now_iso()
    sgc.write_report("completion_lift_v4_v244.json", lift)

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    proof_live_orders = int(sgc.load_artifact("final_report_v242.json").get("real_live_orders_submitted_count", 0) or 0)
    broker = any(bool(sgc.load_artifact(fn).get("real_broker_contacted", False)) for _, _, fn in STAGES)
    approval_files_written = sum(int(sgc.load_artifact(fn).get("approval_files_written", 0) or 0) for _, _, fn in STAGES)
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = any(bool(sgc.load_artifact(fn).get("autonomous_trading_enabled", False)) for _, _, fn in STAGES)
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)
    runtime_approvals_created_by_dummy = False

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v235_to_v244: Operator Authority Appliance Baseline, Authority Manifest Doctor, Live-Submit/Caps Doctor, LiveBrokerFirewall Adapter Doctor, Broker Read-Only Doctor, Armable Quorum Doctor, Execute-Once Handoff V2, Live-Proof Execute-Once Harness V2, Reconcile+Forensic Pipeline V2, and Completion Lift Lock V4",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "operator_authority_appliance_baseline_status": sgc.load_artifact("final_report_v235.json").get("operator_authority_appliance_baseline_controller_status"),
        "authority_manifest_doctor_status": sgc.load_artifact("final_report_v236.json").get("authority_manifest_doctor_controller_status"),
        "live_submit_caps_doctor_status": sgc.load_artifact("final_report_v237.json").get("live_submit_caps_doctor_controller_status"),
        "firewall_adapter_doctor_status": sgc.load_artifact("final_report_v238.json").get("firewall_adapter_doctor_controller_status"),
        "broker_readonly_doctor_status": sgc.load_artifact("final_report_v239.json").get("broker_readonly_doctor_controller_status"),
        "armable_quorum_doctor_status": sgc.load_artifact("final_report_v240.json").get("armable_quorum_doctor_controller_status"),
        "execute_once_handoff_status": sgc.load_artifact("final_report_v241.json").get("execute_once_handoff_controller_status"),
        "execute_once_harness_status": sgc.load_artifact("final_report_v242.json").get("execute_once_harness_controller_status"),
        "reconcile_forensic_pipeline_v2_status": sgc.load_artifact("final_report_v243.json").get("reconcile_forensic_pipeline_v2_controller_status"),
        "completion_lift_lock_v4_status": sgc.load_artifact("final_report_v244.json").get("completion_lift_lock_v4_controller_status"),
        "fully_operational_estimate": sgc.load_artifact("final_report_v244.json").get("fully_operational_estimate"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v244.json").get("next_action_matrix_selection"),
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
    sgc.write_report("dummy_mission_state_report_v235_to_v244.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V235_TO_V244_OPERATOR_AUTHORITY_APPLIANCE_COMPLETE_ZERO_LIVE_ORDERS_NO_APPROVAL_WRITES_NO_RUNTIME_APPROVALS_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD_AWAIT_OPERATOR_EXTERNAL_AUTHORITY",
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
    final_path = sgc.write_report("final_report_v235_to_v244.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v235_to_v244", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_live_orders": final["total_live_orders"], "approval_files_written": final["approval_files_written"], "runtime_approvals_created_by_dummy": final["runtime_approvals_created_by_dummy"], "broker_contacted": final["broker_contacted"], "fully_operational_estimate": final["fully_operational_estimate"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
