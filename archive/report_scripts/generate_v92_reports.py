"""Generate DUMMY v92 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v92 import MILESTONE
from predator_mesh.v92.reports import DEFAULT_REQUIRED_REPORT_NAMES, V92ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = 'v92: Campaign Order 2 Reconcile Edge Degradation And Stop Continue Review'
MISSION_NAME = 'dummy_mission_state_report_v78.json'
FINAL_NAME = "final_report_v92.json"
INDEX_KEYS = ['reconcile_review_controller_status', 'stop_continue_decision_status']


def generate_v92_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V92ReportFactory(**kwargs).build()


def generate_all_v92_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v92_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v92_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v92", INDEX_KEYS)
    sgc.update_tests_summary(92, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(92), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
