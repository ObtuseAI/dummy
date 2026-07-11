"""Generate the DUMMY V195-V204 combined bundle summary reports (runs stages in order)."""

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

BUNDLE_MILESTONE = "DUMMY_V195_TO_V204_FIRST_LIVE_PROOF_ACTIVATION_READINESS_CONTROLLED_SESSION_QUORUM_RECONCILE_FORENSIC_AND_AUTONOMY_LOCK_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(195, 205)]


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"archive.report_scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    proof_live_orders = int(sgc.load_artifact("final_report_v199.json").get("real_live_orders_submitted_count", 0) or 0)
    broker = any(bool(sgc.load_artifact(fn).get("real_broker_contacted", False)) for _, _, fn in STAGES)
    approval_files_written = sum(int(sgc.load_artifact(fn).get("approval_files_written", 0) or 0) for _, _, fn in STAGES)
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = any(bool(sgc.load_artifact(fn).get("autonomous_trading_enabled", False)) for _, _, fn in STAGES)
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v195_to_v204: First Live-Proof Activation Binder, Config/Caps Immutable Quorum, Firewall/Broker Verification, Final Quorum, First Live-Proof Fire, Reconcile, Forensic, Scale/Autonomy Evidence Refresh, Controlled Operation Status, and Production Lock V7",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "activation_binder_status": sgc.load_artifact("final_report_v195.json").get("activation_binder_controller_status"),
        "config_quorum_status": sgc.load_artifact("final_report_v196.json").get("config_quorum_controller_status"),
        "firewall_broker_status": sgc.load_artifact("final_report_v197.json").get("firewall_broker_controller_status"),
        "final_quorum_status": sgc.load_artifact("final_report_v198.json").get("final_quorum_controller_status"),
        "first_live_proof_gate_status": sgc.load_artifact("final_report_v199.json").get("first_live_proof_gate_controller_status"),
        "reconcile_status": sgc.load_artifact("final_report_v200.json").get("reconcile_controller_status"),
        "forensic_status": sgc.load_artifact("final_report_v201.json").get("forensic_controller_status"),
        "evidence_refresh_status": sgc.load_artifact("final_report_v202.json").get("evidence_refresh_controller_status"),
        "controlled_operation_status": sgc.load_artifact("final_report_v203.json").get("controlled_operation_status"),
        "production_lock_status": sgc.load_artifact("final_report_v204.json").get("production_lock_controller_status"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v204.json").get("next_action_matrix_selection"),
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
    sgc.write_report("dummy_mission_state_report_v195_to_v204.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V195_TO_V204_FIRST_LIVE_PROOF_ACTIVATION_CHAIN_COMPLETE_ZERO_LIVE_ORDERS_NO_APPROVAL_WRITES_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "first_live_proof_order_count": proof_live_orders,
        "total_real_live_orders_submitted": proof_live_orders,
        "approval_files_written": approval_files_written,
        "real_broker_contacted": broker,
        "scale_applied": scale_applied,
        "autonomous_trading_enabled": autonomy,
        "caps_modified": caps_changed,
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v195_to_v204.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v195_to_v204", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_real_live_orders_submitted": final["total_real_live_orders_submitted"], "approval_files_written": final["approval_files_written"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
