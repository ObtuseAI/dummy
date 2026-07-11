"""Generate DUMMY v191 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v191 import MILESTONE
from predator_mesh.v191.reports import DEFAULT_REQUIRED_REPORT_NAMES, V191ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = "v191: Limited Autonomy Gate Locked No Live Orders"
MISSION_NAME = "dummy_mission_state_report_v177.json"
FINAL_NAME = "final_report_v191.json"
INDEX_KEYS = ["limited_autonomy_gate_controller_status", "gate_state", "live_orders"]


def generate_v191_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V191ReportFactory(**kwargs).build()


def generate_all_v191_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v191_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v191_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v191", INDEX_KEYS)
    sgc.update_tests_summary(191, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(191), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
