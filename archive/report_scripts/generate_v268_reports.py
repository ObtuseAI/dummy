"""Generate DUMMY v268 reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v268 import MILESTONE
from predator_mesh.v268.reports import (
    DEFAULT_REQUIRED_REPORT_NAMES,
    FINAL_NAME,
    INDEX_KEYS,
    MISSION_NAME,
    VERIFICATION_COMMANDS,
    WORKSTREAM,
    V268ReportFactory,
)

PACK_DIR = ROOT / "operator_authority_pack"
LIVE_SUBMIT_DESC = PACK_DIR / "live_submit_descriptor.json"
CAPS_DESC = PACK_DIR / "caps_descriptor.json"


def _staged_config_kwargs() -> dict[str, Any]:
    """Auto-detect externally staged live-submit/caps descriptors."""
    if not LIVE_SUBMIT_DESC.exists() or not CAPS_DESC.exists():
        return {}
    try:
        live_submit = json.loads(LIVE_SUBMIT_DESC.read_text(encoding="utf-8"))
        caps = json.loads(CAPS_DESC.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {"live_submit_descriptor": live_submit, "caps_descriptor": caps}


def generate_v268_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V268ReportFactory(**kwargs).build()


def generate_all_v268_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v268_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v268_report_bundle(**_staged_config_kwargs())
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v268", INDEX_KEYS)
    sgc.update_tests_summary(268, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(268), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
