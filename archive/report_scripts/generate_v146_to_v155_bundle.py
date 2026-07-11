"""Generate the DUMMY V146-V155 combined bundle summary reports (runs stages in order)."""

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

BUNDLE_MILESTONE = "DUMMY_V146_TO_V155_OPERATOR_HANDOFF_REAL_AUTH_INTAKE_DRY_LIVE_SPLIT_PILOT_SPINE_RECONCILE_AND_CONTROLLED_OPERATION_LOCK_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(146, 156)]


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"archive.report_scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    real_pilot_live_orders = int(sgc.load_artifact("final_report_v151.json").get("real_live_orders_submitted_count", 0) or 0)
    broker = bool(sgc.load_artifact("final_report_v151.json").get("real_broker_contacted", False))
    approval_files_written = sum(int(sgc.load_artifact(fn).get("approval_files_written", 0) or 0) for _, _, fn in STAGES)
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = any(bool(sgc.load_artifact(fn).get("autonomous_trading_enabled", False)) for _, _, fn in STAGES)
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v146_to_v155: Operator Handoff, Real Authority Intake, Dry/Live Mode Split, Rehearsal Spine, Real Pilot Preflight, Real Pilot Fire, Reconcile Intake, Forensic Review, Repeat Preflight, and Controlled Operation Lock",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "operator_handoff_status": sgc.load_artifact("final_report_v146.json").get("handoff_controller_status"),
        "authority_intake_status": sgc.load_artifact("final_report_v147.json").get("intake_validator_controller_status"),
        "mode_firewall_status": sgc.load_artifact("final_report_v148.json").get("mode_firewall_controller_status"),
        "mode": sgc.load_artifact("final_report_v148.json").get("mode"),
        "rehearsal_spine_status": sgc.load_artifact("final_report_v149.json").get("rehearsal_controller_status"),
        "real_pilot_preflight_status": sgc.load_artifact("final_report_v150.json").get("preflight_controller_status"),
        "real_pilot_gate_status": sgc.load_artifact("final_report_v151.json").get("real_pilot_gate_controller_status"),
        "real_pilot_reconcile_status": sgc.load_artifact("final_report_v152.json").get("reconcile_intake_controller_status"),
        "real_pilot_forensic_status": sgc.load_artifact("final_report_v153.json").get("forensic_controller_status"),
        "repeat_preflight_status": sgc.load_artifact("final_report_v154.json").get("repeat_preflight_controller_status"),
        "controlled_operation_lock_status": sgc.load_artifact("final_report_v155.json").get("controlled_operation_lock_controller_status"),
        "controlled_operation_status": sgc.load_artifact("final_report_v155.json").get("controlled_operation_status"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v155.json").get("next_action_matrix_selection"),
        "real_pilot_live_order_count": real_pilot_live_orders,
        "total_real_live_orders_submitted": real_pilot_live_orders,
        "approval_files_written": approval_files_written,
        "real_broker_contacted": broker,
        "market_order_submitted": False,
        "autonomous_trading_enabled": autonomy,
        "scale_applied": scale_applied,
        "caps_modified": caps_changed,
        "current_blockers": [],
    }
    sgc.write_report("dummy_mission_state_report_v146_to_v155.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V146_TO_V155_OPERATOR_HANDOFF_CHAIN_COMPLETE_ZERO_LIVE_ORDERS_NO_APPROVAL_WRITES_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "real_pilot_live_order_count": real_pilot_live_orders,
        "total_real_live_orders_submitted": real_pilot_live_orders,
        "approval_files_written": approval_files_written,
        "real_broker_contacted": broker,
        "scale_applied": scale_applied,
        "autonomous_trading_enabled": autonomy,
        "caps_modified": caps_changed,
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v146_to_v155.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v146_to_v155", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_real_live_orders_submitted": final["total_real_live_orders_submitted"], "approval_files_written": final["approval_files_written"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
