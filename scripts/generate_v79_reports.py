"""Generate DUMMY v79 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v79 import MILESTONE
from predator_mesh.v79.reports import DEFAULT_REQUIRED_REPORT_NAMES, V79ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = 'v79: First Live Canary Forensic Review And Edge Reality Check'
MISSION_NAME = 'dummy_mission_state_report_v65.json'
FINAL_NAME = "final_report_v79.json"
INDEX_KEYS = ['forensic_review_controller_status', 'no_repeat_order_proof_status', 'evidence_to_execution_tieout_status']


def generate_v79_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V79ReportFactory(**kwargs).build()


def generate_all_v79_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v79_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v79_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v79", INDEX_KEYS)
    sgc.update_tests_summary(79, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(79), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
