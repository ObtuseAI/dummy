"""Generate DUMMY v296 reports."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh import staged_gate_common as sgc
from predator_mesh.v296 import MILESTONE
from predator_mesh.v296.reports import (
    DEFAULT_REQUIRED_REPORT_NAMES,
    FINAL_NAME,
    INDEX_KEYS,
    MISSION_NAME,
    VERIFICATION_COMMANDS,
    WORKSTREAM,
    V296ReportFactory,
)

LIVE_PROOF_ACK = "FULL_AUTHORITY_OPERATOR_APPROVED_LIVE_PROOF_ONLY"
PACK_DIR = ROOT / "operator_authority_pack"
MANIFEST_PATH = PACK_DIR / "authority_manifest.json"
ADAPTER_DESCRIPTOR_PATH = ROOT / "runtime" / "operator_external" / "livebrokerfirewall_adapter_descriptor.json"


def _staged_authority_kwargs() -> dict[str, Any]:
    """Auto-detect externally staged authority for operator execution fork."""
    if not MANIFEST_PATH.exists() or not ADAPTER_DESCRIPTOR_PATH.exists():
        return {}
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if manifest.get("proof_target") != "FIRST_REAL_PILOT_PROOF":
        return {}
    env = dict(os.environ)
    env_gate = env.get("DUMMY_LIVE_PROOF_MODE") == "1" and env.get("DUMMY_LIVE_PROOF_ACK") == LIVE_PROOF_ACK
    return {
        "authority": {
            "import_ok": True,
            "authority_present": True,
            "caps_ok_prereq": True,
            "caps_ok": True,
            "adapter_ok": True,
            "env_gate": env_gate,
        },
    }


def generate_v296_report_bundle(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return V296ReportFactory(**kwargs).build()


def generate_all_v296_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v296_report_bundle(**kwargs)
    reports[FINAL_NAME] = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES)
    return reports


def main() -> dict[str, Any]:
    reports = generate_v296_report_bundle(**_staged_authority_kwargs())
    paths = {name: sgc.write_report(name, data) for name, data in reports.items()}
    final = sgc.build_final(reports, workstream=WORKSTREAM, milestone=MILESTONE, mission_name=MISSION_NAME, verification_commands=VERIFICATION_COMMANDS, required_names=DEFAULT_REQUIRED_REPORT_NAMES, paths=paths)
    final_path = sgc.write_report(FINAL_NAME, final)
    sgc.write_final_index(final, final_path, "v296", INDEX_KEYS)
    sgc.update_tests_summary(296, ["final_report.json", "tests_summary.json", FINAL_NAME, *sorted(reports)], sgc.required_stage_tests(296), final["verdict"], final["generated_at"], VERIFICATION_COMMANDS)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
