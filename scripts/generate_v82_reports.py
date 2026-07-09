"""Generate DUMMY v82 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v82 import MILESTONE
from predator_mesh.v82.reports import DEFAULT_REQUIRED_REPORT_NAMES, V82ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = 'v82: Micro-Canary Campaign Gate No Auto-Submit'
MISSION_NAME = 'dummy_mission_state_report_v68.json'
FINAL_NAME = "final_report_v82.json"
INDEX_KEYS = ['campaign_gate_controller_status', 'no_auto_submit_proof_status', 'per_order_approval_requirement_status']


def generate_v82_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V82ReportFactory(**kwargs).build()


def generate_all_v82_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v82_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v82_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v82", INDEX_KEYS)
    sgc.update_tests_summary(82, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(82), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
