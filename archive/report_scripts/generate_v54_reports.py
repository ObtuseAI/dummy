"""Generate DUMMY v54 exact approval actuated inert quarantine reports."""

from __future__ import annotations

import json
import os
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

from predator_mesh.v36.run import EXACT_GATE_ENV
from predator_mesh.v54 import MILESTONE
from predator_mesh.v54.reports import DEFAULT_QUARANTINE_DIR, DEFAULT_REQUIRED_REPORT_NAMES, V54ReportFactory, VERIFICATION_COMMANDS


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _gate_enabled(env: dict[str, str]) -> bool:
    return env.get("DUMMY_PUBLIC_PROBE_MODE") == EXACT_GATE_ENV["DUMMY_PUBLIC_PROBE_MODE"] and env.get("DUMMY_PUBLIC_PROBE_ACK") == EXACT_GATE_ENV["DUMMY_PUBLIC_PROBE_ACK"]


def _approval_from_env(env: dict[str, str]) -> dict[str, Any] | None:
    raw = env.get("DUMMY_V54_APPROVAL_INPUT_JSON")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return {"approval_phrase": "__INVALID_JSON__"}
    return parsed if isinstance(parsed, dict) else {"approval_phrase": "__INVALID_JSON__"}


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


def generate_v54_report_bundle(
    *,
    env: dict[str, str] | None = None,
    enable_real_probe: bool | None = None,
    real_transport: Any | None = None,
    allow_live_network: bool = False,
    approval_input: dict[str, Any] | None = None,
    write_quarantine_artifacts: bool = False,
    quarantine_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    env = {} if env is None else env
    exact_gate = _gate_enabled(env)
    enable_real = exact_gate if enable_real_probe is None else enable_real_probe
    approval = approval_input if approval_input is not None else _approval_from_env(env)
    return V54ReportFactory(
        env=env,
        enable_real_probe=enable_real,
        real_transport=real_transport,
        allow_live_network=allow_live_network,
        approval_input=approval,
        write_quarantine_artifacts=write_quarantine_artifacts,
        quarantine_dir=quarantine_dir,
    ).build()


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    mission = reports["dummy_mission_state_report_v40.json"]
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    final_verdict = "FAIL" if failures else "PASS" if mission.get("mission_state_verdict") == "PASS" else "PARTIAL"
    missing = [name for name in DEFAULT_REQUIRED_REPORT_NAMES if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "v54: Exact Approval Actuated Inert Quarantine Artifact Factory And Release Lock",
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
        '$env:DUMMY_V54_APPROVAL_INPUT_JSON="<exact dedicated approval packet json>"',
        '$env:DUMMY_PUBLIC_PROBE_MODE="1"',
        '$env:DUMMY_PUBLIC_PROBE_ACK="READ_ONLY_PUBLIC_PROBES_ONLY"',
        "python scripts/generate_v54_reports.py",
    ] if final_verdict != "PASS" else [f"Inert quarantine artifacts created under {DEFAULT_QUARANTINE_DIR}; release remains locked."]
    return final


def generate_all_v54_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v54_report_bundle(**kwargs)
    reports["final_report_v54.json"] = _build_final(reports)
    return reports


def _required_v54_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "v54" in path.name or "predator_mesh.v54" in text or "tests.v54_test_helpers" in text:
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
        "approval_controller_status": final.get("approval_controller_status"),
        "artifact_factory_status": final.get("artifact_factory_status"),
        "quarantine_release_lock_status": final.get("quarantine_release_lock_status"),
        "final_report_v54": str(final_path),
        "proof_paths": final.get("proof_paths", {}),
    }
    final_index["v54"] = {"generated_at": final["generated_at"], "milestone": final["milestone"], "verdict": final["verdict"], "final_report_v54": str(final_path), "partial_reason": final["partial_reason"]}
    existing = _load_report("final_report.json", {})
    for key, value in existing.items():
        if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
            final_index[key] = value
    _write_report("final_report.json", final_index)


def main() -> dict[str, Any]:
    env = dict(os.environ)
    gate = _gate_enabled(env)
    approval = _approval_from_env(env)
    reports = generate_v54_report_bundle(env=env, enable_real_probe=gate, allow_live_network=gate, approval_input=approval, write_quarantine_artifacts=approval is not None)
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v54.json", final)
    _write_final_indexes(final, final_path)
    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v54_required_commands"] = VERIFICATION_COMMANDS
    tests_summary["v54_required_tests"] = _required_v54_tests()
    tests_summary["v54_required_reports"] = ["final_report.json", "tests_summary.json", "final_report_v54.json", *sorted(reports)]
    tests_summary["v54_report_generated_at"] = final["generated_at"]
    tests_summary["v54_final_verdict"] = final["verdict"]
    tests_summary["v54_required_test_count"] = len(tests_summary["v54_required_tests"])
    tests_summary["v54_required_report_count"] = len(tests_summary["v54_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
