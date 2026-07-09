"""Generate DUMMY v233 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v233 import MILESTONE
from predator_mesh.v233.reports import DEFAULT_REQUIRED_REPORT_NAMES, V233ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = "v233: Completion Scoreboard V3 Proof Aware Percentages"
MISSION_NAME = "dummy_mission_state_report_v219.json"
FINAL_NAME = "final_report_v233.json"
INDEX_KEYS = ['completion_scoreboard_v3_controller_status', 'fully_operational_estimate', 'first_live_proof_present']


def generate_v233_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V233ReportFactory(**kwargs).build()


def generate_all_v233_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v233_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v233_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v233", INDEX_KEYS)
    sgc.update_tests_summary(233, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(233), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
