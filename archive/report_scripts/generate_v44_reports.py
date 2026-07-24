"""Generate DUMMY V44 read-only observer scaleout reports."""

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
from predator_mesh.v44 import MILESTONE
from predator_mesh.v44.reports import DEFAULT_REQUIRED_REPORT_NAMES, V44ReportFactory, VERIFICATION_COMMANDS


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


def generate_v44_report_bundle(*, env: dict[str, str] | None = None, enable_real_probe: bool | None = None, real_transport: Any | None = None, allow_live_network: bool = False) -> dict[str, dict[str, Any]]:
    env = {} if env is None else env
    exact_gate = _gate_enabled(env)
    enable_real = exact_gate if enable_real_probe is None else enable_real_probe
    return V44ReportFactory(env=env, enable_real_probe=enable_real, real_transport=real_transport, allow_live_network=allow_live_network).build()


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    mission = reports["dummy_mission_state_report_v30.json"]
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    final_verdict = "FAIL" if failures else "PASS" if mission.get("mission_state_verdict") == "PASS" else "PARTIAL"
    missing = [name for name in DEFAULT_REQUIRED_REPORT_NAMES if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "V44: Readonly Observer Scaleout Source Rotation Stability Windows And Execution Lock Hardening",
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
    }
    for key in [
        "mission_state_verdict", "current_next_action", "current_blockers", "exact_gate_status", "ack_decision",
        "v43_carried_status", "v43_baseline_status", "v43_new_real_scored_count", "v43_cumulative_real_scored_count",
        "v43_cumulative_evidence_count", "observer_scaleout_status", "observer_lane_isolation_status",
        "source_rotation_status", "v44_lane_level_counts", "v44_new_real_probe_count", "v44_new_evidence_count",
        "v44_duplicate_stale_excluded_count", "v44_new_settlement_compatible_count", "v44_new_observed_count",
        "v44_new_real_scored_count", "cumulative_evidence_count", "cumulative_real_scored_count",
        "fake_pipeline_score_count", "sample_diversity_status", "sample_quality_status", "calibration_tier",
        "calibration_stability_status", "source_truth_v25_status", "market_class_reliability_v5_status",
        "no_trade_discipline_v5_status", "forecast_quality_ledger_v3_status", "readiness_governor_v4_status",
        "execution_lock_v3_status", "v44_observer_scaleout_audit_ledger_status", "operator_packet", "proof_paths",
    ]:
        if key in mission:
            final[key] = mission[key]
    final["remaining_operator_actions"] = [
        '$env:DUMMY_PUBLIC_PROBE_MODE="1"',
        '$env:DUMMY_PUBLIC_PROBE_ACK="READ_ONLY_PUBLIC_PROBES_ONLY"',
        "python scripts/generate_v43_reports.py",
        "python scripts/generate_v44_reports.py",
    ] if final_verdict != "PASS" else ["Continue read-only observer scaleout; do not enable trading."]
    return final


def generate_all_v44_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v44_report_bundle(**kwargs)
    reports["final_report_v44.json"] = _build_final(reports)
    return reports


def _required_v44_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "v44" in path.name or "predator_mesh.v44" in text or "tests.v44_test_helpers" in text:
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
        "exact_gate_status": final.get("exact_gate_status"),
        "v44_new_real_probe_count": final.get("v44_new_real_probe_count", 0),
        "v44_new_evidence_count": final.get("v44_new_evidence_count", 0),
        "v44_new_real_scored_count": final.get("v44_new_real_scored_count", 0),
        "cumulative_real_scored_count": final.get("cumulative_real_scored_count", 0),
        "final_report_v44": str(final_path),
        "proof_paths": final.get("proof_paths", {}),
    }
    final_index["v44"] = {"generated_at": final["generated_at"], "milestone": final["milestone"], "verdict": final["verdict"], "final_report_v44": str(final_path), "partial_reason": final["partial_reason"]}
    existing = _load_report("final_report.json", {})
    for key, value in existing.items():
        if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
            final_index[key] = value
    _write_report("final_report.json", final_index)


def main() -> dict[str, Any]:
    env = dict(os.environ)
    gate = _gate_enabled(env)
    reports = generate_v44_report_bundle(env=env, enable_real_probe=gate, allow_live_network=gate)
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v44.json", final)
    _write_final_indexes(final, final_path)
    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v44_required_commands"] = VERIFICATION_COMMANDS
    tests_summary["v44_required_tests"] = _required_v44_tests()
    tests_summary["v44_required_reports"] = ["final_report.json", "tests_summary.json", "final_report_v44.json", *sorted(reports)]
    tests_summary["v44_report_generated_at"] = final["generated_at"]
    tests_summary["v44_final_verdict"] = final["verdict"]
    tests_summary["v44_required_test_count"] = len(tests_summary["v44_required_tests"])
    tests_summary["v44_required_report_count"] = len(tests_summary["v44_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
