"""Generate DUMMY V35 V34 QC, frontend build, enabled probe reconciliation, and live score sample expansion reports."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts" / "dummy"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from predator_mesh.v35 import MILESTONE
from predator_mesh.v35.reports import DEFAULT_REQUIRED_REPORT_NAMES, V35ReportFactory
from predator_mesh.v35.run import V34_SMOKE_ENDPOINTS


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
    except Exception as exc:  # pragma: no cover - environment dependent
        print(f"Frontend build could not run: {exc}", file=sys.stderr)
        return False, f"frontend build error: {exc}"


def _smoke_v34_routes() -> tuple[bool, list[str]]:
    try:
        from fastapi.testclient import TestClient

        from dashboard.backend.main import app

        client = TestClient(app)
        failures: list[str] = []
        for endpoint in V34_SMOKE_ENDPOINTS:
            response = client.get(endpoint)
            if response.status_code != 200:
                failures.append(endpoint)
        return not failures, failures
    except Exception as exc:  # pragma: no cover
        print(f"V34 route smoke could not run: {exc}", file=sys.stderr)
        return False, [f"smoke error: {exc}"]


def generate_v35_report_bundle(*, frontend_build_passed: bool, frontend_build_summary: str, route_smoke_ok: bool, route_smoke_failures: list[str]) -> dict[str, dict[str, Any]]:
    return V35ReportFactory(
        frontend_build_passed=frontend_build_passed,
        frontend_build_summary=frontend_build_summary,
        v34_route_smoke_ok=route_smoke_ok,
        v34_route_smoke_failures=route_smoke_failures,
    ).build()


def _required_test_commands() -> list[str]:
    return [
        "python -m pytest tests/ -q --tb=short --timeout=60 --durations=25",
        "cd dashboard/frontend && npm run build",
        "python scripts/generate_v35_reports.py",
    ]


def _required_v35_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "tests.v35_test_helpers" in text or "predator_mesh.v35" in text or "v35_reports" in text:
            tests.append(path.name)
    return tests


def _v35_report_names(reports: dict[str, dict[str, Any]] | None = None) -> list[str]:
    names = sorted((reports or {}).keys())
    return ["final_report.json", "tests_summary.json", "final_report_v35.json", *names]


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None, *, frontend_build_passed: bool, route_smoke_ok: bool) -> dict[str, Any]:
    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v21.json"]
    if not frontend_build_passed or not route_smoke_ok:
        final_verdict = "FAIL"
    else:
        final_verdict = "FAIL" if failures else "PARTIAL" if partials else "PASS"
    all_required = sorted(set(DEFAULT_REQUIRED_REPORT_NAMES))
    missing = [name for name in all_required if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "V35: V34 QC, Frontend Build, Enabled Probe Reconciliation, And Live Score Sample Expansion",
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
            "Set DUMMY_PUBLIC_PROBE_MODE=1 and DUMMY_PUBLIC_PROBE_ACK=READ_ONLY_PUBLIC_PROBES_ONLY for a real read-only public probe run (not fake transport).",
            "Expand the live score sample only after real live-public probe results are produced.",
            "Leave live-submit and caps unchanged.",
        ],
    }
    passthrough_keys = [
        "v34_qc_status",
        "dispatch_overlap_fix_verified",
        "dead_constant_removal_verified",
        "frontend_build_passed",
        "evidence_mode",
        "live_public_eligible",
        "sample_mode",
        "low_sample",
        "sports_source_mode",
        "default_gate_state",
        "default_ack_status",
        "default_probe_run_count",
        "default_live_public_evidence",
        "default_observed",
        "default_live_scored",
        "default_due",
        "default_unresolved",
        "default_sports_mode",
        "default_verdict",
        "enabled_gate_state",
        "enabled_probe_run_count",
        "enabled_evidence",
        "enabled_observed",
        "enabled_scored",
        "enabled_unresolved",
        "enabled_transport_mode",
        "enabled_verdict",
        "v17_truth_loop_status",
        "v21_source_activation_status",
        "v22_forecast_write_status",
        "v23_observer_calibration_status",
        "v24_open_source_public_data_status",
        "v25_market_class_generalization_status",
        "v26_keyless_settlement_expansion_status",
        "v27_integration_settlement_live_scoring_status",
        "v28_oss_observation_closure_status",
        "v29_oss_adapter_spec_factory_status",
        "v30_in_house_adapter_implementation_status",
        "v31_public_probe_execution_status",
        "v32_source_recovery_live_observation_status",
        "v33_operator_enabled_probe_observation_status",
        "v34_operator_enabled_probe_run_reconciliation_status",
        "v34_qc_confirmation_status",
        "dispatch_overlap_fix_verification_status",
        "dead_constant_removal_verification_status",
        "frontend_build_status",
        "default_path_reverification_status",
        "enabled_path_reverification_status",
        "evidence_mode_audit_status",
        "live_score_sample_expansion_readiness",
        "calibration_low_sample_qc_status",
        "v34_route_api_smoke_status",
        "report_transform_consistency_status",
        "protected_hash_reverification_status",
        "no_execution_bridge_deep_recheck_status",
        "sports_fixture_only_reverification_status",
        "source_truth_v16_status",
        "partial_reduction_status",
        "sprint_queue_v12_status",
        "compounding_v19_status",
        "live_submit_flag_status",
        "caps_config_status",
        "direct_order_cancel_bypass_status",
        "no_browser_pageagent_dom_status",
        "no_mined_repo_execution_status",
        "no_secret_leak_status",
        "no_fake_transport_score_claimed_live_status",
        "blunder_separation_status",
        "canonical_identity_status",
        "mission_state_verdict",
        "proof_paths",
    ]
    final.update({key: mission[key] for key in passthrough_keys})
    return final


def generate_all_v35_reports_for_tests(*, frontend_build_passed: bool = True, frontend_build_summary: str = "vite build passed", route_smoke_ok: bool = True, route_smoke_failures: list[str] | None = None) -> dict[str, dict[str, Any]]:
    reports = generate_v35_report_bundle(
        frontend_build_passed=frontend_build_passed,
        frontend_build_summary=frontend_build_summary,
        route_smoke_ok=route_smoke_ok,
        route_smoke_failures=route_smoke_failures or [],
    )
    reports["final_report_v35.json"] = _build_final(reports, frontend_build_passed=frontend_build_passed, route_smoke_ok=route_smoke_ok)
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
        "default_gate_state": final["default_gate_state"],
        "enabled_probe_run_count": final["enabled_probe_run_count"],
        "enabled_scored": final["enabled_scored"],
        "evidence_mode": final["evidence_mode"],
        "sample_mode": final["sample_mode"],
        "frontend_build_passed": final["frontend_build_passed"],
        "live_submit_flag_status": final["live_submit_flag_status"],
        "caps_config_status": final["caps_config_status"],
        "mission_state_verdict": final["mission_state_verdict"],
        "final_report_v35": str(final_path),
        "proof_paths": final["proof_paths"],
    }
    final_index["v35"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v35": str(final_path),
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
    route_smoke_ok, route_smoke_failures = _smoke_v34_routes()
    reports = generate_v35_report_bundle(
        frontend_build_passed=frontend_build_passed,
        frontend_build_summary=frontend_build_summary,
        route_smoke_ok=route_smoke_ok,
        route_smoke_failures=route_smoke_failures,
    )
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths, frontend_build_passed=frontend_build_passed, route_smoke_ok=route_smoke_ok)
    final_path = _write_report("final_report_v35.json", final)
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v35_required_commands"] = _required_test_commands()
    tests_summary["v35_required_tests"] = _required_v35_tests()
    tests_summary["v35_required_reports"] = _v35_report_names(reports)
    tests_summary["v35_report_generated_at"] = final["generated_at"]
    tests_summary["v35_final_verdict"] = final["verdict"]
    tests_summary["v35_frontend_build_passed"] = frontend_build_passed
    tests_summary["v35_v34_route_smoke_ok"] = route_smoke_ok
    tests_summary["v35_required_test_count"] = len(tests_summary["v35_required_tests"])
    tests_summary["v35_required_report_count"] = len(tests_summary["v35_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
