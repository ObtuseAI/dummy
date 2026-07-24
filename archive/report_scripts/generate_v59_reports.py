"""Generate DUMMY v59 end-to-end manual approval consumption inert artifact pipeline reports.

V59 consumes only the manually authored dedicated approval file
(``runtime/approvals/dummy_v55_rehearsal_artifact_approval.json``). Dummy never creates, modifies,
or auto-fills that file. Default operation (no approval file) creates zero quarantine instances.
"""

from __future__ import annotations

import json
import os
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

from predator_mesh.v36.run import EXACT_GATE_ENV
from predator_mesh.v59 import MILESTONE
from predator_mesh.v59.reports import DEFAULT_APPROVAL_INPUT_PATH, DEFAULT_QUARANTINE_DIR, DEFAULT_REQUIRED_REPORT_NAMES, V59ReportFactory, VERIFICATION_COMMANDS


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _gate_enabled(env: dict[str, str]) -> bool:
    return env.get("DUMMY_PUBLIC_PROBE_MODE") == EXACT_GATE_ENV["DUMMY_PUBLIC_PROBE_MODE"] and env.get("DUMMY_PUBLIC_PROBE_ACK") == EXACT_GATE_ENV["DUMMY_PUBLIC_PROBE_ACK"]


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


def generate_v59_report_bundle(
    *,
    env: dict[str, str] | None = None,
    enable_real_probe: bool | None = None,
    real_transport: Any | None = None,
    allow_live_network: bool = False,
    approval_input: dict[str, Any] | None = None,
    approval_path: Path | None = None,
    write_quarantine_artifacts: bool = False,
    quarantine_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    env = {} if env is None else env
    exact_gate = _gate_enabled(env)
    enable_real = exact_gate if enable_real_probe is None else enable_real_probe
    return V59ReportFactory(
        env=env,
        enable_real_probe=enable_real,
        real_transport=real_transport,
        allow_live_network=allow_live_network,
        approval_input=approval_input,
        approval_path=approval_path,
        write_quarantine_artifacts=write_quarantine_artifacts,
        quarantine_dir=quarantine_dir,
    ).build()


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    mission = reports["dummy_mission_state_report_v45.json"]
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    final_verdict = "FAIL" if failures else "PASS" if mission.get("mission_state_verdict") == "PASS" else "PARTIAL"
    missing = [name for name in DEFAULT_REQUIRED_REPORT_NAMES if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "v59: Manual Approval Consumption End-To-End Inert Artifact Pipeline And Release Denial Hardening",
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
        '$env:DUMMY_PUBLIC_PROBE_MODE="1"',
        '$env:DUMMY_PUBLIC_PROBE_ACK="READ_ONLY_PUBLIC_PROBES_ONLY"',
        "python scripts/generate_v59_reports.py",
    ] if final_verdict != "PASS" else [f"Inert quarantine artifacts created and reviewed under {DEFAULT_QUARANTINE_DIR}; release remains locked."]
    return final


def generate_all_v59_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v59_report_bundle(**kwargs)
    reports["final_report_v59.json"] = _build_final(reports)
    return reports


def _required_v59_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "v59" in path.name or "predator_mesh.v59" in text or "tests.v59_test_helpers" in text:
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
        "manual_approval_pipeline_controller_status": final.get("manual_approval_pipeline_controller_status"),
        "inert_quarantine_artifact_factory_v3_status": final.get("inert_quarantine_artifact_factory_v3_status"),
        "artifact_integrity_review_v2_status": final.get("artifact_integrity_review_v2_status"),
        "release_denial_v2_status": final.get("release_denial_v2_status"),
        "final_report_v59": str(final_path),
        "proof_paths": final.get("proof_paths", {}),
    }
    final_index["v59"] = {"generated_at": final["generated_at"], "milestone": final["milestone"], "verdict": final["verdict"], "final_report_v59": str(final_path), "partial_reason": final["partial_reason"]}
    existing = _load_report("final_report.json", {})
    for key, value in existing.items():
        if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
            final_index[key] = value
    _write_report("final_report.json", final_index)


def main() -> dict[str, Any]:
    env = dict(os.environ)
    gate = _gate_enabled(env)
    reports = generate_v59_report_bundle(env=env, enable_real_probe=gate, allow_live_network=gate, write_quarantine_artifacts=True)
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v59.json", final)
    _write_final_indexes(final, final_path)
    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v59_required_commands"] = VERIFICATION_COMMANDS
    tests_summary["v59_required_tests"] = _required_v59_tests()
    tests_summary["v59_required_reports"] = ["final_report.json", "tests_summary.json", "final_report_v59.json", *sorted(reports)]
    tests_summary["v59_report_generated_at"] = final["generated_at"]
    tests_summary["v59_final_verdict"] = final["verdict"]
    tests_summary["v59_required_test_count"] = len(tests_summary["v59_required_tests"])
    tests_summary["v59_required_report_count"] = len(tests_summary["v59_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
