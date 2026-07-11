"""Generate DUMMY v56 rehearsal approval-packet template, operator handoff, and pre-artifact lock reports.

V56 is non-executing. It never writes the dedicated approval file, never creates quarantine
artifact instances, and never infers approval. All packet linting runs in memory only.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = ROOT / "artifacts" / "dummy"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh.v56 import MILESTONE
from predator_mesh.v56.reports import DEFAULT_REQUIRED_REPORT_NAMES, V56ReportFactory, VERIFICATION_COMMANDS


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


def generate_v56_report_bundle() -> dict[str, dict[str, Any]]:
    return V56ReportFactory().build()


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    mission = reports["dummy_mission_state_report_v42.json"]
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    final_verdict = "FAIL" if failures else "PASS" if mission.get("mission_state_verdict") == "PASS" else "PARTIAL"
    missing = [name for name in DEFAULT_REQUIRED_REPORT_NAMES if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "v56: Rehearsal Approval Packet Template Operator Handoff And Pre-Artifact Lock",
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
        "Operator may manually author the dedicated approval file using the V56 template; Dummy will not create it.",
        "Manually place runtime/approvals/dummy_v55_rehearsal_artifact_approval.json with the exact phrase and all acknowledgments.",
        "python scripts/generate_v55_reports.py",
    ] if final_verdict == "PASS" else [
        "Resolve the listed blockers; V56 remains a read-only handoff layer.",
    ]
    return final


def generate_all_v56_reports_for_tests() -> dict[str, dict[str, Any]]:
    reports = generate_v56_report_bundle()
    reports["final_report_v56.json"] = _build_final(reports)
    return reports


def _required_v56_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "v56" in path.name or "predator_mesh.v56" in text or "tests.v56_test_helpers" in text:
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
        "operator_handoff_status": final.get("operator_handoff_status"),
        "approval_packet_linter_status": final.get("approval_packet_linter_status"),
        "pre_artifact_lock_status": final.get("pre_artifact_lock_status"),
        "final_report_v56": str(final_path),
        "proof_paths": final.get("proof_paths", {}),
    }
    final_index["v56"] = {"generated_at": final["generated_at"], "milestone": final["milestone"], "verdict": final["verdict"], "final_report_v56": str(final_path), "partial_reason": final["partial_reason"]}
    existing = _load_report("final_report.json", {})
    for key, value in existing.items():
        if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
            final_index[key] = value
    _write_report("final_report.json", final_index)


def main() -> dict[str, Any]:
    reports = generate_v56_report_bundle()
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v56.json", final)
    _write_final_indexes(final, final_path)
    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v56_required_commands"] = VERIFICATION_COMMANDS
    tests_summary["v56_required_tests"] = _required_v56_tests()
    tests_summary["v56_required_reports"] = ["final_report.json", "tests_summary.json", "final_report_v56.json", *sorted(reports)]
    tests_summary["v56_report_generated_at"] = final["generated_at"]
    tests_summary["v56_final_verdict"] = final["verdict"]
    tests_summary["v56_required_test_count"] = len(tests_summary["v56_required_tests"])
    tests_summary["v56_required_report_count"] = len(tests_summary["v56_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
