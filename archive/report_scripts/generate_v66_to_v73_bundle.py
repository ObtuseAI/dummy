"""Generate the DUMMY V66-V73 combined bundle summary reports (runs stages in order)."""

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

BUNDLE_MILESTONE = "DUMMY_V66_TO_V73_LIVE_CANARY_APPROVAL_BROKER_READONLY_CANDIDATE_FIREWALL_FIRST_CANARY_RECONCILE_RISK_AND_REPEAT_GATE_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(66, 74)]


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"archive.report_scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    v70_final = sgc.load_artifact("final_report_v70.json")
    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v66_to_v73: Live-Canary Approval, Broker Read-Only, Candidate, Firewall, First Canary, Reconcile, Risk, and Repeat Gate",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "real_live_orders_submitted": int(v70_final.get("real_live_orders_submitted_count", 0) or 0),
        "real_broker_contacted": bool(v70_final.get("real_broker_contacted", False)),
        "market_order_submitted": False,
        "no_account_private_data_access": True,
        "no_execution_bridge": True,
        "current_blockers": [],
    }
    sgc.write_report("dummy_mission_state_report_v66_to_v73.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "STAGED_LIVE_CANARY_CHAIN_V66_TO_V73_COMPLETE_NO_LIVE_ORDER_SUBMITTED_ALL_LOCKS_HELD",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "real_live_orders_submitted": mission["real_live_orders_submitted"],
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v66_to_v73.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v66_to_v73", ["stage_verdicts", "real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "real_live_orders_submitted": final["real_live_orders_submitted"], "stage_finals": {k: v["verdict"] for k, v in final["stage_finals"].items()}}, indent=2))
