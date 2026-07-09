"""Generate DUMMY v231 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v231 import MILESTONE
from predator_mesh.v231.reports import DEFAULT_REQUIRED_REPORT_NAMES, V231ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = "v231: Reconcile Forensic Auto Pipeline No New Orders"
MISSION_NAME = "dummy_mission_state_report_v217.json"
FINAL_NAME = "final_report_v231.json"
INDEX_KEYS = ['reconcile_forensic_pipeline_controller_status', 'order_state', 'new_order_placed']


def generate_v231_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V231ReportFactory(**kwargs).build()


def generate_all_v231_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v231_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v231_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v231", INDEX_KEYS)
    sgc.update_tests_summary(231, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(231), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
