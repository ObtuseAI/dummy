"""Generate DUMMY V38 operator-gated read-only public probe completion reports."""

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
from predator_mesh.v38 import MILESTONE
from predator_mesh.v38.reports import DEFAULT_REQUIRED_REPORT_NAMES, V38ReportFactory, VERIFICATION_COMMANDS


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _gate_enabled() -> bool:
    return (
        os.environ.get("DUMMY_PUBLIC_PROBE_MODE") == EXACT_GATE_ENV["DUMMY_PUBLIC_PROBE_MODE"]
        and os.environ.get("DUMMY_PUBLIC_PROBE_ACK") == EXACT_GATE_ENV["DUMMY_PUBLIC_PROBE_ACK"]
    )


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


def generate_v38_report_bundle(
    *,
    frontend_build_passed: bool = True,
    route_smoke_ok: bool = True,
    protected_hashes_ok: bool = True,
    env: dict[str, str] | None = None,
    enable_real_probe: bool | None = None,
    real_transport: Any | None = None,
    allow_live_network: bool = False,
) -> dict[str, dict[str, Any]]:
    env = dict(os.environ) if env is None else env
    exact_gate = (
        env.get("DUMMY_PUBLIC_PROBE_MODE") == EXACT_GATE_ENV["DUMMY_PUBLIC_PROBE_MODE"]
        and env.get("DUMMY_PUBLIC_PROBE_ACK") == EXACT_GATE_ENV["DUMMY_PUBLIC_PROBE_ACK"]
    )
    enable_real = exact_gate if enable_real_probe is None else enable_real_probe
    return V38ReportFactory(
        env=env,
        enable_real_probe=enable_real,
        real_transport=real_transport,
        allow_live_network=allow_live_network,
        frontend_build_passed=frontend_build_passed,
        route_smoke_ok=route_smoke_ok,
        protected_hashes_ok=protected_hashes_ok,
    ).build()


def _build_final(
    reports: dict[str, dict[str, Any]],
    paths: dict[str, Path] | None = None,
    *,
    frontend_build_passed: bool = True,
    route_smoke_ok: bool = True,
) -> dict[str, Any]:
    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v24.json"]
    final_verdict = "FAIL" if failures or not frontend_build_passed or not route_smoke_ok else "PARTIAL" if partials else "PASS"
    missing = [name for name in DEFAULT_REQUIRED_REPORT_NAMES if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "V38: Operator-Gated Real Readonly Probe Completion",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "execution_bridge_present": False,
        "partial_reason": "" if final_verdict == "PASS" else "; ".join(mission.get("current_blockers", [])),
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": {name: str(paths.get(name, ARTIFACTS / name)) for name in reports},
        "required_report_count": len(DEFAULT_REQUIRED_REPORT_NAMES),
        "all_required_reports_generated": not missing,
        "missing_required_reports": missing,
        "failures": failures,
        "partials": partials,
        "verification_commands": VERIFICATION_COMMANDS,
        "remaining_operator_actions": [
            '$env:DUMMY_PUBLIC_PROBE_MODE="1"',
            '$env:DUMMY_PUBLIC_PROBE_ACK="READ_ONLY_PUBLIC_PROBES_ONLY"',
            "python scripts/generate_v38_reports.py",
        ] if mission.get("gate_enabled") is not True else [],
    }
    for key in [
        "mission_state_verdict",
        "current_next_action",
        "next_action",
        "current_blockers",
        "exact_probe_gate_status",
        "real_probe_run_count",
        "real_evidence_count",
        "settlement_compatible_evidence_count",
        "observed_real_live_public_count",
        "real_scored_count",
        "fake_pipeline_score_count",
        "operator_packet",
        "proof_paths",
    ]:
        if key in mission:
            final[key] = mission[key]
    return final


def generate_all_v38_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v38_report_bundle(**kwargs)
    reports["final_report_v38.json"] = _build_final(reports)
    return reports


def _required_v38_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "v38" in path.name or "predator_mesh.v38" in text or "tests.v38_test_helpers" in text:
            tests.append(path.name)
    return tests


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = {
        "generated_at": final["generated_at"],
        "workstream": final["workstream"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "partial_reason": final["partial_reason"],
        "required_report_count": final["required_report_count"],
        "all_required_reports_generated": final["all_required_reports_generated"],
        "current_next_action": final.get("current_next_action"),
        "exact_probe_gate_status": final.get("exact_probe_gate_status"),
        "real_probe_run_count": final.get("real_probe_run_count", 0),
        "real_evidence_count": final.get("real_evidence_count", 0),
        "real_scored_count": final.get("real_scored_count", 0),
        "final_report_v38": str(final_path),
        "proof_paths": final.get("proof_paths", {}),
    }
    final_index["v38"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v38": str(final_path),
        "partial_reason": final["partial_reason"],
    }
    existing = _load_report("final_report.json", {})
    for key, value in existing.items():
        if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
            final_index[key] = value
    _write_report("final_report.json", final_index)


def main() -> dict[str, Any]:
    gate = _gate_enabled()
    reports = generate_v38_report_bundle(enable_real_probe=gate, allow_live_network=gate)
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v38.json", final)
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v38_required_commands"] = VERIFICATION_COMMANDS
    tests_summary["v38_required_tests"] = _required_v38_tests()
    tests_summary["v38_required_reports"] = ["final_report.json", "tests_summary.json", "final_report_v38.json", *sorted(reports)]
    tests_summary["v38_report_generated_at"] = final["generated_at"]
    tests_summary["v38_final_verdict"] = final["verdict"]
    tests_summary["v38_required_test_count"] = len(tests_summary["v38_required_tests"])
    tests_summary["v38_required_report_count"] = len(tests_summary["v38_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))

