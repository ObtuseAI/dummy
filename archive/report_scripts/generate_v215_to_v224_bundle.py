"""Generate the DUMMY V215-V224 operator-activation bundle summary reports (runs stages in order).

Emits the consolidated named artifacts (operator activation packet, zero-broker dry validation, final
arming check, completion scoreboard V2) plus the bundle mission/final reports. Fail-closed: zero live
orders, no broker contact, no approval-file writes by Dummy, no scale, no autonomy.
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

BUNDLE_MILESTONE = "DUMMY_V215_TO_V224_OPERATOR_ACTIVATION_PACKET_DRY_VALIDATION_LIVE_PROOF_EXECUTION_HARNESS_RECONCILE_FORENSIC_AND_NEXT_PHASE_LOCK_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(215, 225)]


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"archive.report_scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    # Emit the consolidated named artifacts from the stage builders / controller reports.
    from predator_mesh.v223.reports import build_scoreboard_v2

    packet = dict(sgc.load_artifact("v215_operator_activation_packet_controller_report.json"))
    packet["generated_at"] = sgc.now_iso()
    packet["read_only"] = True
    sgc.write_report("operator_activation_packet_v215.json", packet)

    dry = dict(sgc.load_artifact("v217_zero_broker_dry_validation_controller_report.json"))
    dry["generated_at"] = sgc.now_iso()
    dry["broker_contacted"] = False
    sgc.write_report("zero_broker_dry_validation_v217.json", dry)

    arming = dict(sgc.load_artifact("v218_final_live_proof_arming_check_controller_report.json"))
    arming["generated_at"] = sgc.now_iso()
    sgc.write_report("final_arming_check_v218.json", arming)

    scoreboard = build_scoreboard_v2()
    scoreboard["generated_at"] = sgc.now_iso()
    sgc.write_report("completion_scoreboard_v223.json", scoreboard)

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    proof_live_orders = int(sgc.load_artifact("final_report_v219.json").get("real_live_orders_submitted_count", 0) or 0)
    broker = any(bool(sgc.load_artifact(fn).get("real_broker_contacted", False)) for _, _, fn in STAGES)
    approval_files_written = sum(int(sgc.load_artifact(fn).get("approval_files_written", 0) or 0) for _, _, fn in STAGES)
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = any(bool(sgc.load_artifact(fn).get("autonomous_trading_enabled", False)) for _, _, fn in STAGES)
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v215_to_v224: Operator Activation Packet, External Authority Manifest Intake, Zero-Broker Dry Validation, Final Live-Proof Arming Check, Hardened Live-Proof Execution Harness, Reconcile Spine V2, Forensic Spine V2, Repeat/Session Bridge V2, Completion Scoreboard V2, and Activation Completion Lock V2",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "operator_activation_packet_status": sgc.load_artifact("final_report_v215.json").get("operator_activation_packet_controller_status"),
        "external_authority_manifest_intake_status": sgc.load_artifact("final_report_v216.json").get("external_authority_manifest_intake_controller_status"),
        "zero_broker_dry_validation_status": sgc.load_artifact("final_report_v217.json").get("zero_broker_dry_validation_controller_status"),
        "final_arming_check_status": sgc.load_artifact("final_report_v218.json").get("final_live_proof_arming_check_controller_status"),
        "hardened_live_proof_status": sgc.load_artifact("final_report_v219.json").get("hardened_live_proof_execution_harness_controller_status"),
        "reconcile_spine_v2_status": sgc.load_artifact("final_report_v220.json").get("reconcile_spine_v2_controller_status"),
        "forensic_spine_v2_status": sgc.load_artifact("final_report_v221.json").get("forensic_spine_v2_controller_status"),
        "repeat_session_bridge_v2_status": sgc.load_artifact("final_report_v222.json").get("route_state"),
        "completion_scoreboard_v2_status": sgc.load_artifact("final_report_v223.json").get("completion_scoreboard_v2_controller_status"),
        "fully_operational_estimate": sgc.load_artifact("final_report_v223.json").get("fully_operational_estimate"),
        "activation_completion_lock_v2_status": sgc.load_artifact("final_report_v224.json").get("activation_completion_lock_v2_controller_status"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v224.json").get("next_action_matrix_selection"),
        "first_live_proof_order_count": proof_live_orders,
        "total_real_live_orders_submitted": proof_live_orders,
        "approval_files_written": approval_files_written,
        "real_broker_contacted": broker,
        "market_order_submitted": False,
        "autonomous_trading_enabled": autonomy,
        "scale_applied": scale_applied,
        "caps_modified": caps_changed,
        "current_blockers": [],
    }
    sgc.write_report("dummy_mission_state_report_v215_to_v224.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V215_TO_V224_OPERATOR_ACTIVATION_CHAIN_COMPLETE_ZERO_LIVE_ORDERS_NO_APPROVAL_WRITES_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD_AWAIT_OPERATOR_EXTERNAL_AUTHORITY_MANIFEST",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "first_live_proof_order_count": proof_live_orders,
        "total_real_live_orders_submitted": proof_live_orders,
        "approval_files_written": approval_files_written,
        "fully_operational_estimate": mission["fully_operational_estimate"],
        "real_broker_contacted": broker,
        "scale_applied": scale_applied,
        "autonomous_trading_enabled": autonomy,
        "caps_modified": caps_changed,
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v215_to_v224.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v215_to_v224", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_real_live_orders_submitted": final["total_real_live_orders_submitted"], "approval_files_written": final["approval_files_written"], "fully_operational_estimate": final["fully_operational_estimate"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
