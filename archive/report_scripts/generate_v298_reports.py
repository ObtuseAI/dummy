"""Generate DUMMY v298 reports."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v298 import MILESTONE
from predator_mesh.v298.reports import (
    ARM_CHECKS,
    DEFAULT_REQUIRED_REPORT_NAMES,
    FINAL_NAME,
    INDEX_KEYS,
    MISSION_NAME,
    VERIFICATION_COMMANDS,
    WORKSTREAM,
    V298ReportFactory,
)

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
PACK_DIR = ROOT / "operator_authority_pack"
MANIFEST_PATH = PACK_DIR / "authority_manifest.json"
APPROVAL_PATH = ROOT / "runtime" / "approvals" / "dummy_controlled_production_pilot_approval.json"
LIVE_SUBMIT_PATH = ROOT / "configs" / "live_submit.json"
CAPS_PATH = ROOT / "configs" / "caps.json"
ADAPTER_DESCRIPTOR_PATH = ROOT / "runtime" / "operator_external" / "livebrokerfirewall_adapter_descriptor.json"


def _validate_approval() -> bool:
    if not APPROVAL_PATH.exists():
        return False
    try:
        approval = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    return approval.get("scope") == "one_controlled_production_pilot_via_firewall_only"


def _live_submit_enabled() -> bool:
    if not LIVE_SUBMIT_PATH.exists():
        return False
    try:
        data = json.loads(LIVE_SUBMIT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(data.get("enabled")) and data.get("proof_scope") == "one_controlled_proof"


def _caps_confirmed() -> bool:
    if not CAPS_PATH.exists():
        return False
    try:
        data = json.loads(CAPS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    # Accept either the explicit first-proof schema or the established repo caps schema.
    limit_only = data.get("order_type_policy") == "LIMIT_ONLY" or data.get("limit_orders_only") is True
    no_market = data.get("market_orders_allowed") is False or data.get("allow_market_orders") is False
    kill_on = data.get("kill_switch_enabled") is True or data.get("kill_switch_required") is True
    order_count_ok = data.get("max_order_count", 1) == 1
    return limit_only and no_market and kill_on and order_count_ok


def _staged_arm_kwargs() -> dict[str, Any]:
    """Build the full-authority arm packet only when every external artifact is present."""
    if not MANIFEST_PATH.exists() or not ADAPTER_DESCRIPTOR_PATH.exists():
        return {}
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if manifest.get("proof_target") != "FIRST_REAL_PILOT_PROOF":
        return {}
    env = dict(os.environ)
    env_mode = env.get("DUMMY_LIVE_PROOF_MODE") == "1"
    env_ack = env.get("DUMMY_LIVE_PROOF_ACK") == LIVE_PROOF_ACK
    if not (env_mode and env_ack):
        return {}
    if not (_validate_approval() and _live_submit_enabled() and _caps_confirmed()):
        return {}
    arm = {key: True for key, _ in ARM_CHECKS}
    arm["env_mode"] = True
    arm["env_ack"] = True
    return {"arm": arm}


def generate_v298_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V298ReportFactory(**kwargs).build()


def generate_all_v298_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v298_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v298_report_bundle(**_staged_arm_kwargs())
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v298", INDEX_KEYS)
    sgc.update_tests_summary(298, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(298), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
