"""Generate DUMMY v221 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v221 import MILESTONE
from predator_mesh.v221.reports import DEFAULT_REQUIRED_REPORT_NAMES, V221ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = "v221: Forensic Spine V2 Proof Reality Risk And Abstention Audit"
MISSION_NAME = "dummy_mission_state_report_v207.json"
FINAL_NAME = "final_report_v221.json"
INDEX_KEYS = ['forensic_spine_v2_controller_status', 'order_state', 'new_order_placed']


def generate_v221_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V221ReportFactory(**kwargs).build()


def generate_all_v221_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v221_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v221_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v221", INDEX_KEYS)
    sgc.update_tests_summary(221, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(221), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
