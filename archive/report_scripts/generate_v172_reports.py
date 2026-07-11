"""Generate DUMMY v172 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v172 import MILESTONE
from predator_mesh.v172.reports import DEFAULT_REQUIRED_REPORT_NAMES, V172ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = "v172: Controlled Operation Readiness Quorum Per Order Only"
MISSION_NAME = "dummy_mission_state_report_v158.json"
FINAL_NAME = "final_report_v172.json"
INDEX_KEYS = ["controlled_operation_quorum_controller_status", "quorum_ready", "autonomous_trading_enabled"]


def generate_v172_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V172ReportFactory(**kwargs).build()


def generate_all_v172_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v172_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v172_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v172", INDEX_KEYS)
    sgc.update_tests_summary(172, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(172), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
