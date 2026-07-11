"""Generate DUMMY v66 live-canary approval packet validator reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v66 import MILESTONE
from predator_mesh.v66.reports import DEFAULT_REQUIRED_REPORT_NAMES, V66ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = "v66: Live-Canary Approval Packet Validator And Live-Submit Preflight Lock"
MISSION_NAME = "dummy_mission_state_report_v52.json"
FINAL_NAME = "final_report_v66.json"
INDEX_KEYS = ["approval_packet_validator_status", "live_submit_config_readonly_checker_status", "no_enable_no_modify_proof_status"]


def generate_v66_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    # Default consumes only the dedicated V70 live-canary approval file (absent by default).
    kwargs.setdefault("approval_path", sgc.V70_LIVE_CANARY_APPROVAL_FILE)
    return V66ReportFactory(**kwargs).build()


def generate_all_v66_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v66_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v66_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v66", INDEX_KEYS)
    sgc.update_tests_summary(66, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(66), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
