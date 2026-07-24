"""Generate DUMMY v57 manual approval-file consumption and inert quarantine instance reports.

V57 consumes only the manually authored dedicated approval file
(``runtime/approvals/dummy_v55_rehearsal_artifact_approval.json``). Dummy never creates or modifies
that file. Default operation (no approval file) creates zero quarantine instances.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.evidence_dir import EvidencePath

ARTIFACTS = EvidencePath(ROOT / "artifacts" / "dummy")

from predator_mesh.v57 import MILESTONE
from predator_mesh.v57.reports import DEFAULT_APPROVAL_INPUT_PATH, DEFAULT_QUARANTINE_DIR, DEFAULT_REQUIRED_REPORT_NAMES, V57ReportFactory, VERIFICATION_COMMANDS


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_report(name: str, data: dict[str, Any]) -> Path:
    path = ARTIFACTS / name
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def _load_report(name: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    path = ARTIFACTS / name
    if not path.exists():
        return fallback or {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback or {}


def generate_v57_report_bundle(
    *,
    approval_input: dict[str, Any] | None = None,
    approval_path: Path | None = None,
    write_quarantine_artifacts: bool = False,
    quarantine_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    return V57ReportFactory(
        approval_input=approval_input,
        approval_path=approval_path,
        write_quarantine_artifacts=write_quarantine_artifacts,
        quarantine_dir=quarantine_dir,
    ).build()


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    mission = reports["dummy_mission_state_report_v43.json"]
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    final_verdict = "FAIL" if failures else "PASS" if mission.get("mission_state_verdict") == "PASS" else "PARTIAL"
    missing = [name for name in DEFAULT_REQUIRED_REPORT_NAMES if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "v57: Manual Approval File Consumption And Inert Quarantine Instance Creation Gate",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "partial_reason": "" if final_verdict == "PASS" else "; ".join(mission.get("current_blockers", [])),
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": {name: str(paths.get(name, ARTIFACTS / name)) for name in reports},
        "required_report_count": len(DEFAULT_REQUIRED_REPORT_NAMES),
        "all_required_reports_generated": not missing,
        "missing_required_reports": missing,
        "failures": failures,
        "partials": sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL"),
        "verification_commands": VERIFICATION_COMMANDS,
    }
    for key, value in mission.items():
        if key not in final:
            final[key] = value
    final["remaining_operator_actions"] = [
        f"Manually author {DEFAULT_APPROVAL_INPUT_PATH} with the exact phrase and all acknowledgments; Dummy will not create it.",
        "python scripts/generate_v57_reports.py",
    ] if final_verdict != "PASS" else [f"Inert quarantine instances created under {DEFAULT_QUARANTINE_DIR}; release remains locked."]
    return final


def generate_all_v57_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v57_report_bundle(**kwargs)
    reports["final_report_v57.json"] = _build_final(reports)
    return reports


def _required_v57_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "v57" in path.name or "predator_mesh.v57" in text or "tests.v57_test_helpers" in text:
            tests.append(path.name)
    return tests


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = {
        "generated_at": final["generated_at"],
        "workstream": final["workstream"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "partial_reason": final["partial_reason"],
        "current_next_action": final.get("current_next_action"),
        "manual_approval_file_consumer_status": final.get("manual_approval_file_consumer_status"),
        "inert_quarantine_instance_factory_v2_status": final.get("inert_quarantine_instance_factory_v2_status"),
        "quarantine_release_lock_v2_status": final.get("quarantine_release_lock_v2_status"),
        "final_report_v57": str(final_path),
        "proof_paths": final.get("proof_paths", {}),
    }
    final_index["v57"] = {"generated_at": final["generated_at"], "milestone": final["milestone"], "verdict": final["verdict"], "final_report_v57": str(final_path), "partial_reason": final["partial_reason"]}
    existing = _load_report("final_report.json", {})
    for key, value in existing.items():
        if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
            final_index[key] = value
    _write_report("final_report.json", final_index)


def main() -> dict[str, Any]:
    reports = generate_v57_report_bundle(write_quarantine_artifacts=True)
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v57.json", final)
    _write_final_indexes(final, final_path)
    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v57_required_commands"] = VERIFICATION_COMMANDS
    tests_summary["v57_required_tests"] = _required_v57_tests()
    tests_summary["v57_required_reports"] = ["final_report.json", "tests_summary.json", "final_report_v57.json", *sorted(reports)]
    tests_summary["v57_report_generated_at"] = final["generated_at"]
    tests_summary["v57_final_verdict"] = final["verdict"]
    tests_summary["v57_required_test_count"] = len(tests_summary["v57_required_tests"])
    tests_summary["v57_required_report_count"] = len(tests_summary["v57_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
