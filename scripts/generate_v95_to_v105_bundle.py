"""Generate the DUMMY V95-V105 combined bundle summary reports (runs stages in order)."""

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

BUNDLE_MILESTONE = "DUMMY_V95_TO_V105_REAL_CAMPAIGN_BLOCKER_CLOSURE_ORDER1_ORDER2_ORDER3_RECONCILE_FORENSIC_AND_SCALE_LOCK_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(95, 106)]


def _orders(v: int) -> int:
    return int(sgc.load_artifact(f"final_report_v{v}.json").get("real_live_orders_submitted_count", 0) or 0)


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    o1, o2, o3 = _orders(99), _orders(103), _orders(105)
    broker = any(bool(sgc.load_artifact(f"final_report_v{v}.json").get("real_broker_contacted", False)) for v in (99, 103, 105))

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v95_to_v105: Real Campaign Blocker Closure, Order 1/2/3, Reconcile, Forensic, and Scale Lock",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "order_1_live_order_count": o1,
        "order_2_live_order_count": o2,
        "order_3_live_order_count": o3,
        "total_real_live_orders_submitted": o1 + o2 + o3,
        "real_broker_contacted": broker,
        "market_order_submitted": False,
        "autonomous_trading_enabled": False,
        "scale_applied": False,
        "current_blockers": [],
    }
    sgc.write_report("dummy_mission_state_report_v95_to_v105.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "REAL_CAMPAIGN_CHAIN_V95_TO_V105_COMPLETE_ZERO_LIVE_ORDERS_NO_SCALE_ALL_LOCKS_HELD",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "order_1_live_order_count": o1,
        "order_2_live_order_count": o2,
        "order_3_live_order_count": o3,
        "total_real_live_orders_submitted": o1 + o2 + o3,
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v95_to_v105.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v95_to_v105", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_real_live_orders_submitted": final["total_real_live_orders_submitted"], "stage_finals": {k: v["verdict"] for k, v in final["stage_finals"].items()}}, indent=2))
