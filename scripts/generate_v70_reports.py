"""Generate DUMMY v70 first tiny live limit-order canary reports.

Default: no firewall adapter, no approval file, no operator live-submit config -> PARTIAL, no submit.
Dummy never enables live-submit, never modifies caps, and never contacts a real broker here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v70 import MILESTONE
from predator_mesh.v70.reports import DEFAULT_REQUIRED_REPORT_NAMES, V70ReportFactory, VERIFICATION_COMMANDS

WORKSTREAM = "v70: First Tiny Live Limit-Order Canary Firewall-Only Explicit Approval"
MISSION_NAME = "dummy_mission_state_report_v56.json"
FINAL_NAME = "final_report_v70.json"
INDEX_KEYS = ["live_canary_controller_status", "pre_submit_checklist_status", "single_submit_guard_status", "post_submit_auto_lock_status"]


def generate_v70_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    # Default consumes only the dedicated V70 approval file (absent by default) and no adapter.
    kwargs.setdefault("approval_path", sgc.V70_LIVE_CANARY_APPROVAL_FILE)
    return V70ReportFactory(**kwargs).build()


def generate_all_v70_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v70_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v70_report_bundle()
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v70", INDEX_KEYS)
    sgc.update_tests_summary(70, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(70), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
