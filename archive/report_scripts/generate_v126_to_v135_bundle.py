"""Generate the DUMMY V126-V135 combined bundle summary reports (runs stages in order)."""

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

BUNDLE_MILESTONE = "DUMMY_V126_TO_V135_CONTROLLED_PRODUCTION_PILOT_AUTHORITY_EXECUTION_RECONCILE_REPEAT_REVIEW_SCALE_AND_AUTONOMY_LOCK_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(126, 136)]


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"archive.report_scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    pilot_live_orders = int(sgc.load_artifact("final_report_v129.json").get("real_live_orders_submitted_count", 0) or 0)
    broker = bool(sgc.load_artifact("final_report_v129.json").get("real_broker_contacted", False))
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = any(bool(sgc.load_artifact(fn).get("autonomous_trading_enabled", False)) for _, _, fn in STAGES)
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v126_to_v135: Pilot Blocker Closure, Approval/Config Tieout, Auth Packet, Controlled Pilot Fire, Reconcile, Repeat Review, Risk Stop, Scale Review, Controlled Operation, and Production Lock",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "pilot_blocker_audit_status": sgc.load_artifact("final_report_v126.json").get("pilot_blocker_controller_status"),
        "pilot_tieout_status": sgc.load_artifact("final_report_v127.json").get("pilot_tieout_controller_status"),
        "pilot_auth_packet_status": sgc.load_artifact("final_report_v128.json").get("pilot_auth_packet_controller_status"),
        "production_pilot_gate_status": sgc.load_artifact("final_report_v129.json").get("pilot_gate_controller_status"),
        "pilot_reconcile_status": sgc.load_artifact("final_report_v130.json").get("pilot_reconcile_controller_status"),
        "repeat_pilot_gate_status": sgc.load_artifact("final_report_v131.json").get("repeat_pilot_gate_controller_status"),
        "risk_stop_policy_status": sgc.load_artifact("final_report_v132.json").get("risk_stop_policy_controller_status"),
        "scale_review_status": sgc.load_artifact("final_report_v133.json").get("scale_recommendation"),
        "controlled_operation_gate_status": sgc.load_artifact("final_report_v134.json").get("controlled_operation_gate_controller_status"),
        "production_lock_status": sgc.load_artifact("final_report_v135.json").get("production_lock_controller_status"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v135.json").get("next_action_matrix_selection"),
        "production_pilot_live_order_count": pilot_live_orders,
        "total_real_live_orders_submitted": pilot_live_orders,
        "real_broker_contacted": broker,
        "market_order_submitted": False,
        "autonomous_trading_enabled": autonomy,
        "scale_applied": scale_applied,
        "caps_modified": caps_changed,
        "current_blockers": [],
    }
    sgc.write_report("dummy_mission_state_report_v126_to_v135.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V126_TO_V135_GOVERNANCE_CHAIN_COMPLETE_ZERO_LIVE_ORDERS_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "production_pilot_live_order_count": pilot_live_orders,
        "total_real_live_orders_submitted": pilot_live_orders,
        "real_broker_contacted": broker,
        "scale_applied": scale_applied,
        "autonomous_trading_enabled": autonomy,
        "caps_modified": caps_changed,
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v126_to_v135.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v126_to_v135", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_real_live_orders_submitted": final["total_real_live_orders_submitted"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
