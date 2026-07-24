"""Generate DUMMY v47 read-only stable-sample threshold closure reports."""

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
from predator_mesh.v47 import MILESTONE
from predator_mesh.v47.reports import DEFAULT_REQUIRED_REPORT_NAMES, V47ReportFactory, VERIFICATION_COMMANDS


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


def generate_v47_report_bundle(*, env: dict[str, str] | None = None, enable_real_probe: bool | None = None, real_transport: Any | None = None, allow_live_network: bool = False) -> dict[str, dict[str, Any]]:
    env = {} if env is None else env
    exact_gate = _gate_enabled(env)
    enable_real = exact_gate if enable_real_probe is None else enable_real_probe
    return V47ReportFactory(env=env, enable_real_probe=enable_real, real_transport=real_transport, allow_live_network=allow_live_network).build()


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    mission = reports["dummy_mission_state_report_v33.json"]
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    final_verdict = "FAIL" if failures else "PASS" if mission.get("mission_state_verdict") == "PASS" else "PARTIAL"
    missing = [name for name in DEFAULT_REQUIRED_REPORT_NAMES if name not in reports]
    final = {
        "generated_at": now_iso(),
        "workstream": "v47: Readonly Stable Sample Candidate Threshold Closure Review And Execution Lock",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "execution_bridge_present": False,
        "order_endpoints_used": False,
        "cancel_endpoints_used": False,
        "order_tickets_created": False,
        "shadow_orders_created": False,
        "dry_submit_packets_created": False,
        "broker_payloads_created": False,
        "execution_rehearsal_created": False,
        "broker_schema_created": False,
        "order_intent_objects_created": False,
        "position_sizing_artifacts_created": False,
        "capital_allocation_artifacts_created": False,
        "portfolio_construction_artifacts_created": False,
        "account_balance_private_position_accessed": False,
        "browser_automation_added": False,
        "pageagent_added": False,
        "mined_repo_executed": False,
        "sports_source_activated": False,
        "fake_transport_score_claimed_live": False,
        "duplicate_evidence_scored_as_new": False,
        "metric_cluster_inflation_scored_as_new": False,
        "live_trading_readiness_claim": False,
        "stable_sample_candidate_live_trading_readiness_claim": False,
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
        "mission_state_verdict",
        "current_next_action",
        "current_blockers",
        "exact_gate_status",
        "ack_decision",
        "v46_baseline_status",
        "v46_new_real_scored_count",
        "v46_cumulative_real_scored_count",
        "v46_cumulative_evidence_count",
        "v46_score_gap_to_100",
        "v46_stable_sample_status",
        "stable_sample_threshold_controller_status",
        "v47_lane_level_counts",
        "v47_new_real_probe_count",
        "v47_new_evidence_count",
        "v47_duplicate_stale_excluded_count",
        "v47_new_settlement_compatible_count",
        "v47_new_observed_count",
        "v47_new_real_scored_count",
        "cumulative_evidence_count",
        "cumulative_real_scored_count",
        "score_gap_to_100",
        "sample_quality_status",
        "sample_diversity_status",
        "temporal_spread_status",
        "metric_cluster_status",
        "source_concentration_status",
        "stable_sample_candidate_status",
        "calibration_tier",
        "calibration_tier_after",
        "calibration_stability_status",
        "calibration_drift_status",
        "source_truth_v28_status",
        "market_class_reliability_v8_status",
        "no_trade_discipline_v8_status",
        "forecast_quality_ledger_v6_status",
        "readiness_governor_v7_status",
        "readiness_exposed_stage",
        "execution_lock_v6_status",
        "operator_packet",
        "proof_paths",
    ]:
        if key in mission:
            final[key] = mission[key]
    final["remaining_operator_actions"] = [
        '$env:DUMMY_PUBLIC_PROBE_MODE="1"',
        '$env:DUMMY_PUBLIC_PROBE_ACK="READ_ONLY_PUBLIC_PROBES_ONLY"',
        "python scripts/generate_v43_reports.py",
        "python scripts/generate_v44_reports.py",
        "python scripts/generate_v45_reports.py",
        "python scripts/generate_v46_reports.py",
        "python scripts/generate_v47_reports.py",
    ] if final_verdict != "PASS" else ["Proceed only with read-only stable-sample review; do not enable trading."]
    return final


def generate_all_v47_reports_for_tests(**kwargs: Any) -> dict[str, dict[str, Any]]:
    reports = generate_v47_report_bundle(**kwargs)
    reports["final_report_v47.json"] = _build_final(reports)
    return reports


def _required_v47_tests() -> list[str]:
    tests: list[str] = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "v47" in path.name or "predator_mesh.v47" in text or "tests.v47_test_helpers" in text:
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
        "v47_new_real_probe_count": final.get("v47_new_real_probe_count", 0),
        "v47_new_evidence_count": final.get("v47_new_evidence_count", 0),
        "v47_new_real_scored_count": final.get("v47_new_real_scored_count", 0),
        "cumulative_real_scored_count": final.get("cumulative_real_scored_count", 0),
        "stable_sample_candidate_status": final.get("stable_sample_candidate_status"),
        "final_report_v47": str(final_path),
        "proof_paths": final.get("proof_paths", {}),
    }
    final_index["v47"] = {"generated_at": final["generated_at"], "milestone": final["milestone"], "verdict": final["verdict"], "final_report_v47": str(final_path), "partial_reason": final["partial_reason"]}
    existing = _load_report("final_report.json", {})
    for key, value in existing.items():
        if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
            final_index[key] = value
    _write_report("final_report.json", final_index)


def main() -> dict[str, Any]:
    env = dict(os.environ)
    gate = _gate_enabled(env)
    reports = generate_v47_report_bundle(env=env, enable_real_probe=gate, allow_live_network=gate)
    paths = {name: _write_report(name, data) for name, data in reports.items()}
    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v47.json", final)
    _write_final_indexes(final, final_path)
    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v47_required_commands"] = VERIFICATION_COMMANDS
    tests_summary["v47_required_tests"] = _required_v47_tests()
    tests_summary["v47_required_reports"] = ["final_report.json", "tests_summary.json", "final_report_v47.json", *sorted(reports)]
    tests_summary["v47_report_generated_at"] = final["generated_at"]
    tests_summary["v47_final_verdict"] = final["verdict"]
    tests_summary["v47_required_test_count"] = len(tests_summary["v47_required_tests"])
    tests_summary["v47_required_report_count"] = len(tests_summary["v47_required_reports"])
    _write_report("tests_summary.json", tests_summary)
    return final


if __name__ == "__main__":
    final = main()
    print(json.dumps({"verdict": final["verdict"], "partial_reason": final["partial_reason"]}, indent=2))
