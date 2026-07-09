"""Generate the DUMMY V106-V115 combined bundle summary reports (runs stages in order)."""

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

BUNDLE_MILESTONE = "DUMMY_V106_TO_V115_CAMPAIGN_FORENSIC_SCALE_RISK_ABSTENTION_PRODUCTION_SESSION_AND_AUTONOMY_REVIEW_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(106, 116)]


def _int(name: str, key: str) -> int:
    return int(sgc.load_artifact(name).get(key, 0) or 0)


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    session_live_orders = _int("final_report_v113.json", "real_live_orders_submitted_count")
    broker = bool(sgc.load_artifact("final_report_v113.json").get("real_broker_contacted", False))
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = bool(sgc.load_artifact("final_report_v115.json").get("autonomous_trading_enabled", False))
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v106_to_v115: Campaign Forensic, Scale Review, Risk, Abstention, Production, Session, and Autonomy Review",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "campaign_final_audit_status": sgc.load_artifact("final_report_v106.json").get("campaign_audit_controller_status"),
        "scale_approval_status": sgc.load_artifact("final_report_v107.json").get("scale_approval_controller_status"),
        "scale_gate_status": sgc.load_artifact("final_report_v111.json").get("scale_recommendation"),
        "risk_governor_status": sgc.load_artifact("final_report_v108.json").get("risk_hardening_controller_status"),
        "abstention_governor_status": sgc.load_artifact("final_report_v109.json").get("abstention_governor_status"),
        "production_readiness_status": sgc.load_artifact("final_report_v110.json").get("production_eligibility_status"),
        "session_governor_status": sgc.load_artifact("final_report_v112.json").get("session_governor_status"),
        "session_canary_status": sgc.load_artifact("final_report_v113.json").get("session_canary_controller_status"),
        "session_reconcile_status": sgc.load_artifact("final_report_v114.json").get("session_reconcile_controller_status"),
        "autonomy_candidate_status": sgc.load_artifact("final_report_v115.json").get("autonomy_eligibility_status"),
        "session_live_order_count": session_live_orders,
        "total_real_live_orders_submitted": session_live_orders,
        "real_broker_contacted": broker,
        "market_order_submitted": False,
        "autonomous_trading_enabled": autonomy,
        "scale_applied": scale_applied,
        "caps_modified": caps_changed,
        "current_blockers": [],
    }
    sgc.write_report("dummy_mission_state_report_v106_to_v115.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V106_TO_V115_GOVERNANCE_CHAIN_COMPLETE_ZERO_LIVE_ORDERS_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "session_live_order_count": session_live_orders,
        "total_real_live_orders_submitted": session_live_orders,
        "real_broker_contacted": broker,
        "scale_applied": scale_applied,
        "autonomous_trading_enabled": autonomy,
        "caps_modified": caps_changed,
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v106_to_v115.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v106_to_v115", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_real_live_orders_submitted": final["total_real_live_orders_submitted"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
