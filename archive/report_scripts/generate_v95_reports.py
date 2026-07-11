"""Generate DUMMY v95 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v95 import MILESTONE
from predator_mesh.v95.reports import DEFAULT_REQUIRED_REPORT_NAMES, V95ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = 'v95: Campaign Blocker Closure Audit V2 And Real Authority Requirement Map'
MISSION_NAME = 'dummy_mission_state_report_v81.json'
FINAL_NAME = "final_report_v95.json"
INDEX_KEYS = ['blocker_closure_controller_status', 'no_submit_proof_status', 'no_broker_contact_proof_status']


def generate_v95_report_bundle() -> dict[str, dict[str, Any]]:
    return V95ReportFactory().build()


def generate_all_v95_reports_for_tests() -> dict[str, dict[str, Any]]:
    reports = generate_v95_report_bundle()
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v95_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v95", INDEX_KEYS)
    sgc.update_tests_summary(95, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(95), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
