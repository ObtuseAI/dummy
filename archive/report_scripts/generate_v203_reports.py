"""Generate DUMMY v203 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v203 import MILESTONE
from predator_mesh.v203.reports import DEFAULT_REQUIRED_REPORT_NAMES, V203ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = "v203: Controlled Operation Status Gate V7 Per Order Only"
MISSION_NAME = "dummy_mission_state_report_v189.json"
FINAL_NAME = "final_report_v203.json"
INDEX_KEYS = ["controlled_operation_status_controller_status", "controlled_operation_status", "autonomous_trading_enabled"]


def generate_v203_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V203ReportFactory(**kwargs).build()


def generate_all_v203_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v203_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v203_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v203", INDEX_KEYS)
    sgc.update_tests_summary(203, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(203), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
