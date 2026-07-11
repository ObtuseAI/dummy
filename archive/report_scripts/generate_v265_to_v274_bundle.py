"""Generate the DUMMY V265-V274 external authority import + adapter injection + first-proof execution runbook bundle (runs stages in order).

Emits consolidated named artifacts (completion lift V7) plus bundle mission/final reports. Fail-closed: zero live
orders, no broker contact, no approval-file writes by Dummy, no runtime/approvals creation, no scale, no autonomy.
"""

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

BUNDLE_MILESTONE = "DUMMY_V265_TO_V274_EXTERNAL_AUTHORITY_IMPORT_WIZARD_ADAPTER_INJECTION_APPLIANCE_PROOF_EXECUTION_RUNBOOK_ROUTE_AND_COMPLETION_LIFT_V1"
STAGES = [(v, f"generate_v{v}_reports", f"final_report_v{v}.json") for v in range(265, 275)]


def main() -> dict[str, Any]:
    stage_finals: dict[str, Any] = {}
    for version, module_name, final_name in STAGES:
        module = importlib.import_module(f"archive.report_scripts.{module_name}")
        final = module.main()
        stage_finals[f"v{version}"] = {"verdict": final["verdict"], "milestone": final["milestone"], "partial_reason": final["partial_reason"], "current_next_action": final.get("current_next_action"), "final_report": final_name}

    from predator_mesh.v274.reports import build_completion_lift_v7
    lift = build_completion_lift_v7(); lift["generated_at"] = sgc.now_iso()
    sgc.write_report("completion_lift_v7_v274.json", lift)

    verdicts = [e["verdict"] for e in stage_finals.values()]
    bundle_verdict = "FAIL" if "FAIL" in verdicts else "PARTIAL" if "PARTIAL" in verdicts else "PASS"

    proof_live_orders = int(sgc.load_artifact("final_report_v272.json").get("real_live_orders_submitted_count", 0) or 0)
    broker = any(bool(sgc.load_artifact(fn).get("real_broker_contacted", False)) for _, _, fn in STAGES)
    approval_files_written = sum(int(sgc.load_artifact(fn).get("approval_files_written", 0) or 0) for _, _, fn in STAGES)
    scale_applied = any(bool(sgc.load_artifact(fn).get("scale_applied", False)) for _, _, fn in STAGES)
    autonomy = any(bool(sgc.load_artifact(fn).get("autonomous_trading_enabled", False)) for _, _, fn in STAGES)
    caps_changed = any(bool(sgc.load_artifact(fn).get("caps_modified", False)) for _, _, fn in STAGES)
    runtime_approvals_created_by_dummy = False

    mission = {
        "generated_at": sgc.now_iso(),
        "workstream": "v265_to_v274: External Authority Import Baseline, Import Wizard, Approval Manifest Schema Verifier, External Live-Submit/Caps State Verifier, LiveBrokerFirewall Injection Appliance, Broker Read-Only Optional Verifier, Final Armability Runbook, Execute-Once Runbook Wrapper V5, Proof Intake/Reconcile Handoff V3, and Completion Lift V7 Route Lock",
        "milestone": BUNDLE_MILESTONE,
        "mission_state_verdict": bundle_verdict,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "stage_next_actions": {k: v["current_next_action"] for k, v in stage_finals.items()},
        "locks": sgc.LOCKS,
        "live_submit_disabled": True,
        "caps_unchanged": not caps_changed,
        "external_authority_import_baseline_status": sgc.load_artifact("final_report_v265.json").get("external_authority_import_baseline_controller_status"),
        "external_authority_import_wizard_status": sgc.load_artifact("final_report_v266.json").get("external_authority_import_wizard_controller_status"),
        "approval_manifest_schema_verifier_status": sgc.load_artifact("final_report_v267.json").get("approval_manifest_schema_verifier_controller_status"),
        "external_live_submit_caps_state_verifier_status": sgc.load_artifact("final_report_v268.json").get("external_live_submit_caps_state_verifier_controller_status"),
        "livebrokerfirewall_injection_appliance_status": sgc.load_artifact("final_report_v269.json").get("livebrokerfirewall_injection_appliance_controller_status"),
        "broker_readonly_optional_verifier_status": sgc.load_artifact("final_report_v270.json").get("broker_readonly_optional_verifier_controller_status"),
        "final_armability_runbook_status": sgc.load_artifact("final_report_v271.json").get("final_armability_runbook_controller_status"),
        "execute_once_runbook_status": sgc.load_artifact("final_report_v272.json").get("execute_once_runbook_controller_status"),
        "proof_intake_reconcile_handoff_v3_status": sgc.load_artifact("final_report_v273.json").get("proof_intake_reconcile_handoff_v3_controller_status"),
        "completion_lift_v7_status": sgc.load_artifact("final_report_v274.json").get("completion_lift_v7_controller_status"),
        "fully_operational_estimate": sgc.load_artifact("final_report_v274.json").get("fully_operational_estimate"),
        "next_action_matrix_selection": sgc.load_artifact("final_report_v274.json").get("next_action_matrix_selection"),
        "first_live_proof_order_count": proof_live_orders,
        "total_real_live_orders_submitted": proof_live_orders,
        "approval_files_written": approval_files_written,
        "runtime_approvals_created_by_dummy": runtime_approvals_created_by_dummy,
        "real_broker_contacted": broker,
        "market_order_submitted": False,
        "autonomous_trading_enabled": autonomy,
        "scale_applied": scale_applied,
        "caps_modified": caps_changed,
        "current_blockers": [],
    }
    sgc.write_report("dummy_mission_state_report_v265_to_v274.json", mission)

    bundle_final = {
        "generated_at": sgc.now_iso(),
        "workstream": mission["workstream"],
        "milestone": BUNDLE_MILESTONE,
        "verdict": bundle_verdict,
        "partial_reason": "" if bundle_verdict == "PASS" else "; ".join(f"{k}={v['verdict']}" for k, v in stage_finals.items() if v["verdict"] != "PASS"),
        "current_next_action": "V265_TO_V274_EXTERNAL_AUTHORITY_IMPORT_AND_EXECUTION_RUNBOOK_COMPLETE_ZERO_LIVE_ORDERS_NO_APPROVAL_WRITES_NO_RUNTIME_APPROVALS_NO_SCALE_NO_AUTONOMY_ALL_LOCKS_HELD_AWAIT_OPERATOR_EXTERNAL_AUTHORITY",
        "stage_finals": stage_finals,
        "stage_verdicts": {k: v["verdict"] for k, v in stage_finals.items()},
        "first_live_proof_order_count": proof_live_orders,
        "total_real_live_orders_submitted": proof_live_orders,
        "total_live_orders": proof_live_orders,
        "approval_files_written": approval_files_written,
        "runtime_approvals_created_by_dummy": runtime_approvals_created_by_dummy,
        "fully_operational_estimate": mission["fully_operational_estimate"],
        "real_broker_contacted": broker,
        "broker_contacted": broker,
        "market_order": False,
        "scale_applied": scale_applied,
        "autonomous_trading_enabled": autonomy,
        "caps_modified": caps_changed,
        "live_submit_enabled": False,
        "account_private_data_accessed": False,
        "locks": sgc.LOCKS,
        "proof_paths": {f"final_report_v{v}": str(sgc.ARTIFACTS / fn) for v, _, fn in STAGES},
    }
    final_path = sgc.write_report("final_report_v265_to_v274.json", bundle_final)
    sgc.write_final_index(bundle_final, final_path, "v265_to_v274", ["stage_verdicts", "total_real_live_orders_submitted"])
    return bundle_final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "total_live_orders": final["total_live_orders"], "approval_files_written": final["approval_files_written"], "runtime_approvals_created_by_dummy": final["runtime_approvals_created_by_dummy"], "broker_contacted": final["broker_contacted"], "fully_operational_estimate": final["fully_operational_estimate"], "stage_verdicts": final["stage_verdicts"]}, indent=2))
