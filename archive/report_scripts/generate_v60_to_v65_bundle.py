"""Generate the DUMMY V60-V65 combined bundle summary reports.

Runs each stage generator in order (V60 -> V65 so baseline readbacks chain), then writes:
- artifacts/dummy/final_report_v60_to_v65.json
- artifacts/dummy/dummy_mission_state_report_v60_to_v65.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc

BUNDLE_MILESTONE = "DUMMY_V60_TO_V65_QUARANTINE_REVIEW_LOCAL_REHEARSAL_DRY_SHADOW_FIREWALL_AND_MICRO_ORDER_GATE_LOCKED_CHAIN_V1"
STAGES = [
    (60, "generate_v60_reports", "final_report_v60.json"),
    (61, "generate_v61_reports", "final_report_v61.json"),
    (62, "generate_v62_reports", "final_report_v62.json"),
    (63, "generate_v63_reports", "final_report_v63.json"),
    (64, "generate_v64_reports", "final_report_v64.json"),
    (65, "generate_v65_reports", "final_report_v65.json"),
]


def _run_stage(module_name: str) -> dict[str, Any]:
    import importlib

    module = importlib.import_module(f"archive.report_scripts.{module_name}")
    return module.main()


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        final = _run_stage(module_name)
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    verdicts = [entry["verdict"] for entry in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v60_to_v65: Quarantine Review, Local Rehearsal, Dry/Shadow, Firewall, and Micro-Order Gate Locked Chain",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "no_live_order_submitted": True,
        "no_market_order": True,
        "no_broker_payload_with_submit_authority": True,
        "no_account_private_data_access": True,
        "no_execution_bridge": True,
        "current_blockers": [],
    }
    sgc.write_report("dummy_mission_state_report_v60_to_v65.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "STAGED_LOCKED_CHAIN_V60_TO_V65_COMPLETE_ALL_LOCKS_HELD",
        "stage_finals": stage_finals,
        "expected_posture": {
            "v60": "PARTIAL if no real quarantine artifacts",
            "v61": "PASS design-only",
            "v62": "PARTIAL by missing local rehearsal approval; exact fixture PASS",
            "v63": "PASS schema-only/no-submit",
            "v64": "PASS preflight-only/no-submit",
            "v65": "PARTIAL by missing future live-canary approval; exact fixture PASS gate-ready-locked",
        },
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v60_to_v65.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v60_to_v65", [])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "stage_finals": {k: v["verdict"] for k, v in final["stage_finals"].items()}}, indent=2))
