"""Generate DUMMY v77 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v77 import MILESTONE
from predator_mesh.v77.reports import DEFAULT_REQUIRED_REPORT_NAMES, V77ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = 'v77: First Tiny Live Limit-Order Canary Fire On Full Auth Only'
MISSION_NAME = 'dummy_mission_state_report_v63.json'
FINAL_NAME = "final_report_v77.json"
INDEX_KEYS = ['live_canary_controller_status', 'single_submit_guard_status', 'post_submit_auto_lock_status']


def generate_v77_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V77ReportFactory(**kwargs).build()


def generate_all_v77_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v77_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v77_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v77", INDEX_KEYS)
    sgc.update_tests_summary(77, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(77), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
