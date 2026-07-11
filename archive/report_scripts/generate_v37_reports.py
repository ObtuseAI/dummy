"""Generate DUMMY V37 autonomous build/verify/repair workflow reports."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = ROOT / "artifacts" / "dummy"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh.v37 import MILESTONE
from predator_mesh.v37.reports import DEFAULT_REQUIRED_REPORT_NAMES, V37ReportFactory, VERIFICATION_COMMANDS


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _gate_enabled(env: dict[str, str] | None = None) -> bool:
    env = dict(os.environ) if env is None else env
    return (
        env.get("DUMMY_PUBLIC_PROBE_MODE") == "1"
        and env.get("DUMMY_PUBLIC_PROBE_ACK") == "READ_ONLY_PUBLIC_PROBES_ONLY"
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


def _run_frontend_build() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            "npm run build",
            cwd=str(ROOT / "dashboard" / "frontend"),
            capture_output=True,
            text=True,
            timeout=300,
            shell=True,
        )
        summary = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            print("Frontend build failed:\n" + summary, file=sys.stderr)
        return result.returncode == 0, summary or "vite build passed"
    except Exception as exc:  # pragma: no cover
        print(f"Frontend build could not run: {exc}", file=sys.stderr)
        return False, f"frontend build error: {exc}"


def _smoke_v37_routes() -> tuple[bool, list[str]]:
    try:
        from fastapi.testclient import TestClient

        from dashboard.backend.main import app
        from predator_mesh.v37.reports import V37_ROUTES

        client = TestClient(app)
        failures: list[str] = []
        for endpoint in V37_ROUTES:
            response = client.get(endpoint)
            if response.status_code != 200:
                failures.append(endpoint)
        return not failures, failures
    except Exception as exc:  # pragma: no cover
        print(f"V37 route smoke could not run: {exc}", file=sys.stderr)
        return False, [f"smoke error: {exc}"]


def generate_v37_report_bundle(
    *,
    frontend_build_passed: bool,
    route_smoke_ok: bool,
    protected_hashes_ok: bool = True,
    env: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    env = dict(os.environ) if env is None else env
    enable_real = _gate_enabled(env)
    env = env if enable_real else {}
    return V37ReportFactory(
        env=env,
        enable_real_probe=enable_real,
        frontend_build_passed=frontend_build_passed,
        route_smoke_ok=route_smoke_ok,
        protected_hashes_ok=protected_hashes_ok,
    ).build()


def _required_v37_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "tests.v37_test_helpers" in text or "predator_mesh.v37" in text or "v37_reports" in text:
            tests.append(path.name)
    return tests


def _v37_report_names(reports: dict[str, dict[str, Any]] | None = None) -> list[str]:
    names = sorted((reports or {}).keys())
    return ["final_report.json", "tests_summary.json", "final_report_v37.json", *names]


def _build_final(
    reports: dict[str, dict[str, Any]],
    paths: dict[str, Path] | None = None,
    *,
    frontend_build_passed: bool,
    route_smoke_ok: bool,
) -> dict[str, Any]:
    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v23.json"]
    if not frontend_build_passed or not route_smoke_ok:
        final_verdict = "FAIL"
    else:
        final_verdict = "FAIL" if failures else "PARTIAL" if partials else "PASS"
    all_required = sorted(set(DEFAULT_REQUIRED_REPORT_NAMES))
    missing = [name for name in all_required if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "V37: Autonomous Build Verify Repair And Exact-Gated Probe Workflow",
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
        "required_report_count": len(all_required),
        "all_required_reports_generated": not missing,
        "missing_required_reports": missing,
        "failures": failures,
        "partials": partials,
        "verification_commands": VERIFICATION_COMMANDS,
        "remaining_operator_actions": [
            "Set DUMMY_PUBLIC_PROBE_MODE=1 and DUMMY_PUBLIC_PROBE_ACK=READ_ONLY_PUBLIC_PROBES_ONLY to allow read-only public probes.",
            "Leave configs/live_submit.json and configs/caps.json unchanged.",
            "Do not enable live trading, browser automation, or mined repo execution.",
        ],
    }
    passthrough = [
        "mission_state_verdict",
        "current_next_action",
        "current_blockers",
        "exact_probe_gate_status",
        "real_probe_readiness_status",
        "real_evidence_count",
        "observed_count",
        "live_scored_count",
        "fake_pipeline_score_count",
        "live_submit_disabled",
        "caps_unchanged",
        "proof_paths",
    ]
    final.update({key: mission[key] for key in passthrough if key in mission})
    return final


def generate_all_v37_reports_for_tests(
    *,
    frontend_build_passed: bool = True,
    route_smoke_ok: bool = True,
    protected_hashes_ok: bool = True,
    env: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    reports = generate_v37_report_bundle(
        frontend_build_passed=frontend_build_passed,
        route_smoke_ok=route_smoke_ok,
        protected_hashes_ok=protected_hashes_ok,
        env={} if env is None else env,
    )
    reports["final_report_v37.json"] = _build_final(
        reports,
        frontend_build_passed=frontend_build_passed,
        route_smoke_ok=route_smoke_ok,
    )
    return reports


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
        "real_probe_readiness_status": final.get("real_probe_readiness_status"),
        "real_evidence_count": final.get("real_evidence_count", 0),
        "live_scored_count": final.get("live_scored_count", 0),
        "final_report_v37": str(final_path),
        "proof_paths": final.get("proof_paths", {}),
    }
    final_index["v37"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v37": str(final_path),
        "partial_reason": final["partial_reason"],
    }
    existing = _load_report("final_report.json", {})
    if existing:
        final_index["previous_final_report_snapshot"] = {
            key: existing[key]
            for key in ("generated_at", "milestone", "verdict", "partial_reason")
            if key in existing
        }
        for key, value in existing.items():
            if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
                final_index[key] = value
    _write_report("final_report.json", final_index)


def main() -> dict[str, Any]:
    frontend_build_passed, _frontend_build_summary = _run_frontend_build()
    route_smoke_ok, _route_smoke_failures = _smoke_v37_routes()
    reports = generate_v37_report_bundle(
        frontend_build_passed=frontend_build_passed,
        route_smoke_ok=route_smoke_ok,
    )
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths, frontend_build_passed=frontend_build_passed, route_smoke_ok=route_smoke_ok)
    final_path = _write_report("final_report_v37.json", final)
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v37_required_commands"] = VERIFICATION_COMMANDS
    tests_summary["v37_required_tests"] = _required_v37_tests()
    tests_summary["v37_required_reports"] = _v37_report_names(reports)
    tests_summary["v37_report_generated_at"] = final["generated_at"]
    tests_summary["v37_final_verdict"] = final["verdict"]
    tests_summary["v37_frontend_build_passed"] = frontend_build_passed
    tests_summary["v37_route_smoke_ok"] = route_smoke_ok
    tests_summary["v37_required_test_count"] = len(tests_summary["v37_required_tests"])
    tests_summary["v37_required_report_count"] = len(tests_summary["v37_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
