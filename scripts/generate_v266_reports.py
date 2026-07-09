"""Generate DUMMY v266 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v266 import MILESTONE
from predator_mesh.v266.reports import (
    DEFAULT_REQUIRED_REPORT_NAMES,
    FINAL_NAME,
    INDEX_KEYS,
    MISSION_NAME,
    VERIFICATION_COMMANDS,
    WORKSTREAM,
    V266ReportFactory,
)

APPROVAL_PATH = ROOT / "runtime" / "approvals" / "dummy_controlled_production_pilot_approval.json"
PACK_DIR = ROOT / "operator_authority_pack"


def _staged_authority_kwargs() -> dict[str, Any]:
    """Auto-detect externally staged operator authority without mutating it."""
    if not APPROVAL_PATH.exists() or not (PACK_DIR / "authority_manifest.json").exists():
        return {}
    try:
        approval = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        "import_approval": approval,
        "live_submit_descriptor": True,
        "caps_descriptor": True,
        "firewall_descriptor": True,
    }


def generate_v266_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V266ReportFactory(**kwargs).build()


def generate_all_v266_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v266_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v266_report_bundle(**_staged_authority_kwargs())
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v266", INDEX_KEYS)
    sgc.update_tests_summary(266, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(266), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
