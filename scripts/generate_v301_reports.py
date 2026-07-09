"""Generate DUMMY v301 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v301 import MILESTONE
from predator_mesh.v301.reports import (
    DEFAULT_REQUIRED_REPORT_NAMES,
    FINAL_NAME,
    INDEX_KEYS,
    MISSION_NAME,
    VERIFICATION_COMMANDS,
    WORKSTREAM,
    V301ReportFactory,
)

V298_FINAL = ROOT / "artifacts" / "dummy" / "final_report_v298.json"


def _staged_route_kwargs() -> dict[str, Any]:
    """Route autopilot after the v298 execute-once final proof artifact."""
    if not V298_FINAL.exists():
        return {}
    try:
        v298 = json.loads(V298_FINAL.read_text(encoding="utf-8"))
    except Exception:
        return {}
    status = str(v298.get("execute_once_final_proof_runner_v7_controller_status", ""))
    if status != "PASS_EXECUTE_ONCE_FINAL_PROOF_RUNNER_SUBMITTED_AUTOLOCKED":
        return {}
    return {
        "real_proof": True,
        "reconcile": True,
        "forensic": True,
        "route": "repeat",
        "repair_required": False,
        "stop": True,
    }


def generate_v301_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V301ReportFactory(**kwargs).build()


def generate_all_v301_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v301_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v301_report_bundle(**_staged_route_kwargs())
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v301", INDEX_KEYS)
    sgc.update_tests_summary(301, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(301), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
