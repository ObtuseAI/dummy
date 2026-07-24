"""Generate DUMMY V36 exact-gate real read-only public probe run and live sample expansion reports."""

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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.evidence_dir import EvidencePath

ARTIFACTS = EvidencePath(ROOT / "artifacts" / "dummy")

from predator_mesh.v36 import MILESTONE
from predator_mesh.v36.reports import DEFAULT_REQUIRED_REPORT_NAMES, V36ReportFactory

V35_SMOKE_ENDPOINTS = [
    "/api/v35/v34-qc",
    "/api/v35/frontend-build",
    "/api/v35/default-path",
    "/api/v35/enabled-path",
    "/api/v35/evidence-mode",
    "/api/v35/live-score-sample-readiness",
    "/api/v35/calibration-low-sample",
    "/api/v35/v34-route-smoke",
    "/api/v35/report-transform-consistency",
    "/api/v35/protected-hash",
    "/api/v35/no-execution-bridge-deep-recheck",
    "/api/v35/sports-fixture-only",
    "/api/v35/source-truth-v16",
    "/api/v35/partial-reduction",
    "/api/v35/sprint-v12",
    "/api/v35/compounding-v19",
    "/api/v35/market-class-scoreboard",
    "/api/v35/mission-state",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _gate_enabled(env: dict[str, str] | None = None) -> bool:
    env = dict(os.environ) if env is None else env
    return env.get("DUMMY_PUBLIC_PROBE_MODE") == "1" and env.get("DUMMY_PUBLIC_PROBE_ACK") == "READ_ONLY_PUBLIC_PROBES_ONLY"


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
        passed = result.returncode == 0
        if not passed:
            print("Frontend build failed:\n" + summary, file=sys.stderr)
        return passed, summary or ("vite build " + ("passed" if passed else "failed"))
    except Exception as exc:  # pragma: no cover
        print(f"Frontend build could not run: {exc}", file=sys.stderr)
        return False, f"frontend build error: {exc}"


def _smoke_v35_routes() -> tuple[bool, list[str]]:
    try:
        from fastapi.testclient import TestClient

        from dashboard.backend.main import app

        client = TestClient(app)
        failures: list[str] = []
        for endpoint in V35_SMOKE_ENDPOINTS:
            response = client.get(endpoint)
            if response.status_code != 200:
                failures.append(endpoint)
        return not failures, failures
    except Exception as exc:  # pragma: no cover
        print(f"V35 route smoke could not run: {exc}", file=sys.stderr)
        return False, [f"smoke error: {exc}"]


def generate_v36_report_bundle(
    *,
    frontend_build_passed: bool,
    frontend_build_summary: str,
    route_smoke_ok: bool,
    route_smoke_failures: list[str],
    env: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    env = dict(os.environ) if env is None else env
    enable_real = _gate_enabled(env)
    env = env if enable_real else {}
    if enable_real:
        print("V36 exact gate detected at runtime; real read-only public probe pass enabled.", file=sys.stderr)
    return V36ReportFactory(
        enable_real_probe=enable_real,
        env=env,
        frontend_build_passed=frontend_build_passed,
        frontend_build_summary=frontend_build_summary,
        v35_route_smoke_ok=route_smoke_ok,
        v35_route_smoke_failures=route_smoke_failures,
    ).build()


def _required_test_commands() -> list[str]:
    return [
        "python -m pytest tests/ -q --tb=short --timeout=60 --durations=25",
        "cd dashboard/frontend && npm run build",
        "python scripts/generate_v36_reports.py",
    ]


def _required_v36_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "tests.v36_test_helpers" in text or "predator_mesh.v36" in text or "v36_reports" in text:
            tests.append(path.name)
    return tests


def _v36_report_names(reports: dict[str, dict[str, Any]] | None = None) -> list[str]:
    names = sorted((reports or {}).keys())
    return ["final_report.json", "tests_summary.json", "final_report_v36.json", *names]


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
    mission = reports["dummy_mission_state_report_v22.json"]
    if not frontend_build_passed or not route_smoke_ok:
        final_verdict = "FAIL"
    else:
        final_verdict = "FAIL" if failures else "PARTIAL" if partials else "PASS"
    all_required = sorted(set(DEFAULT_REQUIRED_REPORT_NAMES))
    missing = [name for name in all_required if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "V36: Exact-Gate Real Read-Only Public Probe Run And Live Sample Expansion",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "execution_bridge_present": False,
        "partial_reason": "" if final_verdict == "PASS" else "; ".join(mission["partial_reasons"]),
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": {name: str(paths.get(name, ARTIFACTS / name)) for name in reports},
        "required_report_count": len(all_required),
        "all_required_reports_generated": not missing,
        "missing_required_reports": missing,
        "failures": failures,
        "partials": partials,
        "remaining_operator_actions": [
            "Set DUMMY_PUBLIC_PROBE_MODE=1 and DUMMY_PUBLIC_PROBE_ACK=READ_ONLY_PUBLIC_PROBES_ONLY for a real read-only public probe run.",
            "Expand the live score sample only after real live-public probe results are produced.",
            "Leave live-submit and caps unchanged.",
        ],
    }
    passthrough_keys = [
        "gate_snapshot",
        "gate_enabled",
        "ack_decision",
        "real_probe_run_count",
        "real_evidence_count",
        "real_observed_count",
        "real_scored_count",
        "real_calibrated_count",
        "real_unresolved_count",
        "fake_pipeline_scores",
        "mission_state_verdict",
        "live_submit_disabled",
        "caps_unchanged",
        "no_browser_automation",
        "no_mined_code",
        "proof_paths",
    ]
    final.update({key: mission[key] for key in passthrough_keys if key in mission})
    return final


def generate_all_v36_reports_for_tests(
    *,
    frontend_build_passed: bool = True,
    frontend_build_summary: str = "vite build passed",
    route_smoke_ok: bool = True,
    route_smoke_failures: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    reports = generate_v36_report_bundle(
        frontend_build_passed=frontend_build_passed,
        frontend_build_summary=frontend_build_summary,
        route_smoke_ok=route_smoke_ok,
        route_smoke_failures=route_smoke_failures or [],
        env={} if env is None else env,
    )
    reports["final_report_v36.json"] = _build_final(
        reports, frontend_build_passed=frontend_build_passed, route_smoke_ok=route_smoke_ok
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
        "gate_enabled": final.get("gate_enabled", False),
        "real_probe_run_count": final.get("real_probe_run_count", 0),
        "real_scored_count": final.get("real_scored_count", 0),
        "mission_state_verdict": final.get("mission_state_verdict", "PARTIAL"),
        "final_report_v36": str(final_path),
        "proof_paths": final.get("proof_paths", {}),
    }
    final_index["v36"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v36": str(final_path),
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
    frontend_build_passed, frontend_build_summary = _run_frontend_build()
    route_smoke_ok, route_smoke_failures = _smoke_v35_routes()
    reports = generate_v36_report_bundle(
        frontend_build_passed=frontend_build_passed,
        frontend_build_summary=frontend_build_summary,
        route_smoke_ok=route_smoke_ok,
        route_smoke_failures=route_smoke_failures,
    )
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths, frontend_build_passed=frontend_build_passed, route_smoke_ok=route_smoke_ok)
    final_path = _write_report("final_report_v36.json", final)
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v36_required_commands"] = _required_test_commands()
    tests_summary["v36_required_tests"] = _required_v36_tests()
    tests_summary["v36_required_reports"] = _v36_report_names(reports)
    tests_summary["v36_report_generated_at"] = final["generated_at"]
    tests_summary["v36_final_verdict"] = final["verdict"]
    tests_summary["v36_frontend_build_passed"] = frontend_build_passed
    tests_summary["v36_v35_route_smoke_ok"] = route_smoke_ok
    tests_summary["v36_required_test_count"] = len(tests_summary["v36_required_tests"])
    tests_summary["v36_required_report_count"] = len(tests_summary["v36_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
