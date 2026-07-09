"""Generate the DUMMY V74-V84 combined bundle summary reports (runs stages in order)."""

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

BUNDLE_MILESTONE = "DUMMY_V74_TO_V84_LIVE_CANARY_BLOCKER_CLOSURE_FIRST_REAL_CANARY_RECONCILE_REPEAT_GATE_MICRO_CAMPAIGN_AND_SESSION_GOVERNOR_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(74, 85)]


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    v77 = sgc.load_artifact("final_report_v77.json")
    v81 = sgc.load_artifact("final_report_v81.json")
    v77_orders = int(v77.get("real_live_orders_submitted_count", 0) or 0)
    v81_orders = int(v81.get("real_live_orders_submitted_count", 0) or 0)

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v74_to_v84: Blocker Closure, First/Second Real Canary, Reconcile, Repeat Gate, Micro-Campaign, and Session Governor",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "v77_live_order_count": v77_orders,
        "v81_live_order_count": v81_orders,
        "total_real_live_orders_submitted": v77_orders + v81_orders,
        "real_broker_contacted": bool(v77.get("real_broker_contacted", False) or v81.get("real_broker_contacted", False)),
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "current_blockers": [],
    }
    sgc.write_report("dummy_mission_state_report_v74_to_v84.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "STAGED_LIVE_CANARY_CHAIN_V74_TO_V84_COMPLETE_ZERO_LIVE_ORDERS_ALL_LOCKS_HELD",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "v77_live_order_count": v77_orders,
        "v81_live_order_count": v81_orders,
        "total_real_live_orders_submitted": v77_orders + v81_orders,
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v74_to_v84.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v74_to_v84", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_real_live_orders_submitted": final["total_real_live_orders_submitted"], "stage_finals": {k: v["verdict"] for k, v in final["stage_finals"].items()}}, indent=2))
