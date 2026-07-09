"""Generate DUMMY v111 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v111 import MILESTONE
from predator_mesh.v111.reports import DEFAULT_REQUIRED_REPORT_NAMES, V111ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = 'v111: Operator Approved Scale Step 1 Gate No Auto Scale'
MISSION_NAME = 'dummy_mission_state_report_v97.json'
FINAL_NAME = "final_report_v111.json"
INDEX_KEYS = ['scale_gate_controller_status', 'scale_recommendation', 'no_caps_modification_proof_status']


def generate_v111_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V111ReportFactory(**kwargs).build()


def generate_all_v111_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v111_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v111_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v111", INDEX_KEYS)
    sgc.update_tests_summary(111, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(111), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
