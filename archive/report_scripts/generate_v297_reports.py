"""Generate DUMMY v297 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v297 import MILESTONE
from predator_mesh.v297.reports import (
    DEFAULT_REQUIRED_REPORT_NAMES,
    FINAL_NAME,
    INDEX_KEYS,
    MISSION_NAME,
    VERIFICATION_COMMANDS,
    WORKSTREAM,
    V297ReportFactory,
)

PACK_DIR = ROOT / "operator_authority_pack"
MANIFEST_PATH = PACK_DIR / "authority_manifest.json"
ADAPTER_DESCRIPTOR_PATH = ROOT / "runtime" / "operator_external" / "livebrokerfirewall_adapter_descriptor.json"
APPROVAL_PATH = ROOT / "runtime" / "approvals" / "dummy_controlled_production_pilot_approval.json"
REQUIRED_SCOPE = "one_controlled_production_pilot_via_firewall_only"


def _staged_seal_kwargs() -> dict[str, Any]:
    """Auto-detect externally staged authority and arm the command seal."""
    if not MANIFEST_PATH.exists() or not ADAPTER_DESCRIPTOR_PATH.exists() or not APPROVAL_PATH.exists():
        return {}
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        approval = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if manifest.get("proof_target") != "FIRST_REAL_PILOT_PROOF":
        return {}
    if approval.get("scope") != REQUIRED_SCOPE:
        return {}
    return {
        "seal": {
            "authority_ready": True,
            "proof_target": "FIRST_REAL_PILOT_PROOF",
            "idempotency_key": "operator-staged-k1",
            "adapter_descriptor": {"firewall": True},
            "manifest": {"version": "v3"},
        },
    }


def generate_v297_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V297ReportFactory(**kwargs).build()


def generate_all_v297_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v297_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v297_report_bundle(**_staged_seal_kwargs())
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v297", INDEX_KEYS)
    sgc.update_tests_summary(297, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(297), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
