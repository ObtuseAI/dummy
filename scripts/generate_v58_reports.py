"""Generate DUMMY v58 quarantined rehearsal-artifact reviewer and release-denial proof reports.

V58 is non-executing and read-only. It reviews existing inert quarantined artifacts (none in the
default repository state), validates integrity, and proves release/transform is denied. It never
creates the approval file, never creates or mutates quarantine artifacts in the default path.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts" / "dummy"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh.v58 import MILESTONE
from predator_mesh.v58.reports import DEFAULT_REQUIRED_REPORT_NAMES, V58ReportFactory, VERIFICATION_COMMANDS


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


def generate_v58_report_bundle(*, quarantine_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    return V58ReportFactory(quarantine_dir=quarantine_dir).build()


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    mission = reports["dummy_mission_state_report_v44.json"]
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    final_verdict = "FAIL" if failures else "PASS" if mission.get("mission_state_verdict") == "PASS" else "PARTIAL"
    missing = [name for name in DEFAULT_REQUIRED_REPORT_NAMES if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "v58: Quarantined Rehearsal Artifact Reviewer And Release Denial Proof",
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
        "No quarantine artifacts exist in the default repo; V58 is a read-only reviewer.",
        "Operator may manually author the dedicated approval file to let V57 create inert instances; Dummy will not create it.",
    ] if final_verdict != "PASS" else ["Reviewed inert quarantine artifacts pass integrity; release remains locked."]
    return final


def generate_all_v58_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v58_report_bundle(**kwargs)
    reports["final_report_v58.json"] = _build_final(reports)
    return reports


def _required_v58_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "v58" in path.name or "predator_mesh.v58" in text or "tests.v58_test_helpers" in text:
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
        "quarantine_artifact_reviewer_status": final.get("quarantine_artifact_reviewer_status"),
        "artifact_integrity_validator_status": final.get("artifact_integrity_validator_status"),
        "release_denial_proof_status": final.get("release_denial_proof_status"),
        "final_report_v58": str(final_path),
        "proof_paths": final.get("proof_paths", {}),
    }
    final_index["v58"] = {"generated_at": final["generated_at"], "milestone": final["milestone"], "verdict": final["verdict"], "final_report_v58": str(final_path), "partial_reason": final["partial_reason"]}
    existing = _load_report("final_report.json", {})
    for key, value in existing.items():
        if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
            final_index[key] = value
    _write_report("final_report.json", final_index)


def main() -> dict[str, Any]:
    reports = generate_v58_report_bundle()
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v58.json", final)
    _write_final_indexes(final, final_path)
    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v58_required_commands"] = VERIFICATION_COMMANDS
    tests_summary["v58_required_tests"] = _required_v58_tests()
    tests_summary["v58_required_reports"] = ["final_report.json", "tests_summary.json", "final_report_v58.json", *sorted(reports)]
    tests_summary["v58_report_generated_at"] = final["generated_at"]
    tests_summary["v58_final_verdict"] = final["verdict"]
    tests_summary["v58_required_test_count"] = len(tests_summary["v58_required_tests"])
    tests_summary["v58_required_report_count"] = len(tests_summary["v58_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
