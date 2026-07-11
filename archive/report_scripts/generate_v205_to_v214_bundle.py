"""Generate the DUMMY V205-V214 completion-accelerator bundle summary reports (runs stages in order)."""

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

BUNDLE_MILESTONE = "DUMMY_V205_TO_V214_COMPLETION_ACCELERATOR_OPERATOR_ACTIVATION_COCKPIT_LIVE_PROOF_RUNNER_RECONCILE_SPINE_AND_COMPLETION_SCOREBOARD_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(205, 215)]


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"archive.report_scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    # Emit the three consolidated artifacts from the runner builders.
    from predator_mesh.v207.reports import build_cockpit_snapshot
    from predator_mesh.v208.reports import resolve_authority
    from predator_mesh.v213.reports import build_scoreboard
    cockpit = build_cockpit_snapshot(); cockpit["generated_at"] = sgc.now_iso(); cockpit["read_only"] = True
    sgc.write_report("activation_cockpit_v207.json", cockpit)
    resolver = resolve_authority(); resolver["generated_at"] = sgc.now_iso()
    sgc.write_report("authority_resolver_v208.json", resolver)
    scoreboard = build_scoreboard(); scoreboard["generated_at"] = sgc.now_iso()
    sgc.write_report("completion_scoreboard_v213.json", scoreboard)

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    proof_live_orders = int(sgc.load_artifact("final_report_v209.json").get("real_live_orders_submitted_count", 0) or 0)
    broker = any(bool(sgc.load_artifact(fn).get("real_broker_contacted", False)) for _, _, fn in STAGES)
    approval_files_written = sum(int(sgc.load_artifact(fn).get("approval_files_written", 0) or 0) for _, _, fn in STAGES)
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = any(bool(sgc.load_artifact(fn).get("autonomous_trading_enabled", False)) for _, _, fn in STAGES)
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v205_to_v214: Completion Accelerator Baseline, Activation Manifest, Activation Cockpit, Authority Resolver, Live-Proof Runner, Reconcile Runner, Forensic Runner, Repeat/Session Bridge, Completion Scoreboard, and Completion Accelerator Lock",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "completion_baseline_status": sgc.load_artifact("final_report_v205.json").get("completion_baseline_controller_status"),
        "activation_manifest_status": sgc.load_artifact("final_report_v206.json").get("activation_manifest_controller_status"),
        "activation_cockpit_status": sgc.load_artifact("final_report_v207.json").get("cockpit_controller_status"),
        "authority_resolver_status": sgc.load_artifact("final_report_v208.json").get("authority_state"),
        "live_proof_runner_status": sgc.load_artifact("final_report_v209.json").get("live_proof_runner_controller_status"),
        "reconcile_runner_status": sgc.load_artifact("final_report_v210.json").get("reconcile_runner_controller_status"),
        "forensic_runner_status": sgc.load_artifact("final_report_v211.json").get("forensic_runner_controller_status"),
        "repeat_session_bridge_status": sgc.load_artifact("final_report_v212.json").get("route_state"),
        "completion_scoreboard_status": sgc.load_artifact("final_report_v213.json").get("completion_scoreboard_controller_status"),
        "fully_operational_estimate": sgc.load_artifact("final_report_v213.json").get("fully_operational_estimate"),
        "completion_accelerator_lock_status": sgc.load_artifact("final_report_v214.json").get("completion_accelerator_lock_controller_status"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v214.json").get("next_action_matrix_selection"),
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
    sgc.write_report("dummy_mission_state_report_v205_to_v214.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V205_TO_V214_COMPLETION_ACCELERATOR_CHAIN_COMPLETE_ZERO_LIVE_ORDERS_NO_APPROVAL_WRITES_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD",
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
    final_path = sgc.write_report("final_report_v205_to_v214.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v205_to_v214", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_real_live_orders_submitted": final["total_real_live_orders_submitted"], "approval_files_written": final["approval_files_written"], "fully_operational_estimate": final["fully_operational_estimate"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
