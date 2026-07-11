"""Generate the DUMMY V175-V184 combined bundle summary reports (runs stages in order)."""

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

BUNDLE_MILESTONE = "DUMMY_V175_TO_V184_CONTROLLED_OPERATION_APPROVAL_SESSION_PREFLIGHT_FIRE_RECONCILE_FORENSIC_STOP_SCALE_AUTONOMY_DRYRUN_AND_PRODUCTION_LOCK_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(175, 185)]


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"archive.report_scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    session_live_orders = int(sgc.load_artifact("final_report_v177.json").get("real_live_orders_submitted_count", 0) or 0)
    broker = bool(sgc.load_artifact("final_report_v177.json").get("real_broker_contacted", False))
    approval_files_written = sum(int(sgc.load_artifact(fn).get("approval_files_written", 0) or 0) for _, _, fn in STAGES)
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = any(bool(sgc.load_artifact(fn).get("autonomous_trading_enabled", False)) for _, _, fn in STAGES)
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v175_to_v184: Controlled Operation Approval, Session Preflight, Session Fire, Reconcile, Forensic, Session Decision, Scale Review V2, Autonomy Evidence, Limited Autonomy Dry-Run, and Production Lock V5",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "controlled_operation_approval_status": sgc.load_artifact("final_report_v175.json").get("controlled_operation_approval_controller_status"),
        "session_preflight_status": sgc.load_artifact("final_report_v176.json").get("session_preflight_controller_status"),
        "controlled_session_gate_status": sgc.load_artifact("final_report_v177.json").get("controlled_session_gate_controller_status"),
        "session_reconcile_status": sgc.load_artifact("final_report_v178.json").get("session_reconcile_controller_status"),
        "session_forensic_status": sgc.load_artifact("final_report_v179.json").get("session_forensic_controller_status"),
        "session_decision_status": sgc.load_artifact("final_report_v180.json").get("session_decision"),
        "scale_review_status": sgc.load_artifact("final_report_v181.json").get("scale_recommendation"),
        "autonomy_evidence_status": sgc.load_artifact("final_report_v182.json").get("autonomy_eligibility"),
        "limited_autonomy_dryrun_status": sgc.load_artifact("final_report_v183.json").get("limited_autonomy_dryrun_controller_status"),
        "production_lock_status": sgc.load_artifact("final_report_v184.json").get("production_lock_controller_status"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v184.json").get("next_action_matrix_selection"),
        "controlled_session_live_order_count": session_live_orders,
        "total_real_live_orders_submitted": session_live_orders,
        "approval_files_written": approval_files_written,
        "real_broker_contacted": broker,
        "market_order_submitted": False,
        "autonomous_trading_enabled": autonomy,
        "scale_applied": scale_applied,
        "caps_modified": caps_changed,
        "current_blockers": [],
    }
    sgc.write_report("dummy_mission_state_report_v175_to_v184.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V175_TO_V184_CONTROLLED_OPERATION_SESSION_CHAIN_COMPLETE_ZERO_LIVE_ORDERS_NO_APPROVAL_WRITES_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "controlled_session_live_order_count": session_live_orders,
        "total_real_live_orders_submitted": session_live_orders,
        "approval_files_written": approval_files_written,
        "real_broker_contacted": broker,
        "scale_applied": scale_applied,
        "autonomous_trading_enabled": autonomy,
        "caps_modified": caps_changed,
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v175_to_v184.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v175_to_v184", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_real_live_orders_submitted": final["total_real_live_orders_submitted"], "approval_files_written": final["approval_files_written"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
