"""Generate DUMMY V28 read-only public observation closure reports."""

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

from predator_mesh.v28 import MILESTONE
from predator_mesh.v28.reports import REPORT_NAMES, V28ReportFactory


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_report(name: str, data: dict[str, Any]) -> Path:
    path = ARTIFACTS / name
    path.parent.mkdir(parents=True, exist_ok=True)
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


def generate_v28_report_bundle(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    return V28ReportFactory(enable_network=enable_network).build()


def _required_test_commands() -> list[str]:
    return [
        "python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60",
        "python -m pytest tests/ -q --tb=short --timeout=60",
        "cd dashboard/frontend && npm run build",
        "python scripts/generate_v28_reports.py",
    ]


def _required_v28_tests() -> list[str]:
    tests_dir = ROOT / "tests"
    tests: list[str] = []
    for path in sorted(tests_dir.glob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "tests.v28_test_helpers" in text:
            tests.append(path.name)
    return tests


def _v28_report_names(reports: dict[str, dict[str, Any]] | None = None) -> list[str]:
    names = sorted((reports or generate_v28_report_bundle(enable_network=False)).keys())
    return ["final_report.json", "tests_summary.json", "final_report_v28.json", *names]


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v14.json"]
    final_verdict = "FAIL" if failures else "PARTIAL" if partials else "PASS"
    report_paths = {name: str(paths.get(name, ARTIFACTS / name)) for name in reports}
    return {
        "generated_at": now_iso(),
        "workstream": "V28: Read-Only Public Probe Activation Observation Closure And Live Score Seed",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "execution_bridge_present": False,
        "trading_endpoints_used": False,
        "cancel_endpoints_used": False,
        "private_endpoints_used": False,
        "order_endpoints_used": False,
        "github_repo_code_executed": False,
        "mined_repo_code_imported": False,
        "partial_reason": "" if final_verdict == "PASS" else "; ".join(mission["partial_reasons"]),
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": report_paths,
        "failures": failures,
        "partials": partials,
        "v17_truth_loop_status": mission["v17_truth_loop_status"],
        "v21_source_activation_status": mission["v21_source_activation_status"],
        "v22_forecast_write_status": mission["v22_forecast_write_status"],
        "v23_observer_calibration_status": mission["v23_observer_calibration_status"],
        "v24_open_source_public_data_status": mission["v24_open_source_public_data_status"],
        "v25_market_class_generalization_status": mission["v25_market_class_generalization_status"],
        "v26_keyless_settlement_expansion_status": mission["v26_keyless_settlement_expansion_status"],
        "v27_integration_settlement_live_scoring_status": mission["v27_integration_settlement_live_scoring_status"],
        "live_submit_enabled": mission["live_submit_enabled"],
        "live_submit_flag_status": mission["live_submit_flag_status"],
        "caps_config_status": mission["caps_config_status"],
        "explicit_integration_mode_gate_status": mission["explicit_integration_mode_gate_status"],
        "integration_enabled_state": mission["integration_enabled_state"],
        "public_probe_runner_status": mission["public_probe_runner_status"],
        "public_probe_run_count": mission["public_probe_run_count"],
        "cached_probe_evidence_status": mission["cached_probe_evidence_status"],
        "cached_evidence_mode_split": mission["cached_evidence_mode_split"],
        "observation_normalizer_status": mission["observation_normalizer_status"],
        "settlement_disambiguation_status": mission["settlement_disambiguation_status"],
        "source_unavailable_recovery_status": mission["source_unavailable_recovery_status"],
        "due_observation_closure_status": mission["due_observation_closure_status"],
        "due_forecast_count": mission["due_forecast_count"],
        "observed_forecast_count": mission["observed_forecast_count"],
        "live_score_seed_status": mission["live_score_seed_status"],
        "live_scored_count": mission["live_scored_count"],
        "live_unresolved_count": mission["live_unresolved_count"],
        "live_calibration_seed_status": mission["live_calibration_seed_status"],
        "sports_source_decision_status": mission["sports_source_decision_status"],
        "sports_source_mode": mission["sports_source_mode"],
        "kalshi_ambiguity_reduction_status": mission["kalshi_ambiguity_reduction_status"],
        "forecast_cadence_v4_status": mission["forecast_cadence_v4_status"],
        "forecast_write_count": mission["forecast_write_count"],
        "no_trade_write_count": mission["no_trade_write_count"],
        "observer_queue_count": mission["observer_queue_count"],
        "live_observer_loop_v4_status": mission["live_observer_loop_v4_status"],
        "live_source_truth_v10_status": mission["live_source_truth_v10_status"],
        "partial_to_pass_closure_status": mission["partial_to_pass_closure_status"],
        "partial_causes_before": mission["partial_causes_before"],
        "partial_causes_after": mission["partial_causes_after"],
        "adapter_sprint_v5_status": mission["adapter_sprint_v5_status"],
        "compounding_v12_status": mission["compounding_v12_status"],
        "next_bundle_recommendation": mission["next_bundle_recommendation"],
        "market_class_scoreboard_v13_status": mission["market_class_scoreboard_v13_status"],
        "mission_state_verdict": mission["mission_state_verdict"],
        "github_gap_fill_status": mission["github_gap_fill_status"],
        "github_candidate_count": mission["github_candidate_count"],
        "github_domain_counts": mission["github_domain_counts"],
        "no_secret_leak_status": mission["no_secret_leak_status"],
        "no_source_api_key_leak_status": mission["no_source_api_key_leak_status"],
        "no_github_token_leak_status": mission["no_github_token_leak_status"],
        "no_kalshi_private_key_leak_status": mission["no_kalshi_private_key_leak_status"],
        "no_direct_order_bypass_status": mission["no_direct_order_bypass_status"],
        "no_direct_cancel_bypass_status": mission["no_direct_cancel_bypass_status"],
        "no_unauthorized_source_status": mission["no_unauthorized_source_status"],
        "no_questionable_odds_scraping_status": mission["no_questionable_odds_scraping_status"],
        "no_unapproved_source_activation_status": mission["no_unapproved_source_activation_status"],
        "no_commercial_source_without_approval_status": mission["no_commercial_source_without_approval_status"],
        "no_premium_feed_required_global_blocker_status": mission["no_premium_feed_required_global_blocker_status"],
        "no_fixture_claimed_real_status": mission["no_fixture_claimed_real_status"],
        "no_replay_claimed_live_status": mission["no_replay_claimed_live_status"],
        "no_replay_score_claimed_live_status": mission["no_replay_score_claimed_live_status"],
        "no_proxy_claimed_exchange_native_status": mission["no_proxy_claimed_exchange_native_status"],
        "no_cached_sample_claimed_live_status": mission["no_cached_sample_claimed_live_status"],
        "no_stale_cached_evidence_scored_live_status": mission["no_stale_cached_evidence_scored_live_status"],
        "no_context_claimed_edge_status": mission["no_context_claimed_edge_status"],
        "no_example_market_canonical_center_status": mission["no_example_market_canonical_center_status"],
        "no_unresolved_forecast_scored_status": mission["no_unresolved_forecast_scored_status"],
        "no_ambiguous_settlement_scored_status": mission["no_ambiguous_settlement_scored_status"],
        "no_source_unavailable_forecast_scored_status": mission["no_source_unavailable_forecast_scored_status"],
        "no_not_due_forecast_scored_status": mission["no_not_due_forecast_scored_status"],
        "no_outcome_fabrication_status": mission["no_outcome_fabrication_status"],
        "no_integration_gate_to_execution_bridge_status": mission["no_integration_gate_to_execution_bridge_status"],
        "no_public_probe_runner_to_execution_bridge_status": mission["no_public_probe_runner_to_execution_bridge_status"],
        "no_cached_evidence_to_execution_bridge_status": mission["no_cached_evidence_to_execution_bridge_status"],
        "no_observation_closure_to_execution_bridge_status": mission["no_observation_closure_to_execution_bridge_status"],
        "no_live_score_seed_to_execution_bridge_status": mission["no_live_score_seed_to_execution_bridge_status"],
        "no_live_calibration_seed_to_execution_bridge_status": mission["no_live_calibration_seed_to_execution_bridge_status"],
        "no_source_truth_to_execution_bridge_status": mission["no_source_truth_to_execution_bridge_status"],
        "no_adapter_sprint_to_execution_bridge_status": mission["no_adapter_sprint_to_execution_bridge_status"],
        "blunder_separation_status": mission["blunder_separation_status"],
        "dashboard_status": mission["dashboard_status"],
        "proof_paths": mission["proof_paths"],
        "remaining_operator_actions": [
            "Set DUMMY_PUBLIC_INTEGRATION_MODE=1 and DUMMY_PUBLIC_INTEGRATION_CONFIRM=READ_ONLY_PUBLIC_PROBES before real public probes.",
            "Supply fresh live-public or valid cached-live-public evidence before any live score seed.",
            "Approve a terms-safe sports schedule/status source or keep sports fixture/replay-only.",
            "Keep Bloomberg and other keyed/licensed feeds optional, never required global blockers.",
        ],
    }


def generate_all_v28_reports_for_tests(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    reports = generate_v28_report_bundle(enable_network=enable_network)
    reports["final_report_v28.json"] = _build_final(reports)
    return reports


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = dict(final)
    final_index["final_report_v28"] = str(final_path)
    final_index["v28"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v28": str(final_path),
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
    (ARTIFACTS / "final_report.json").write_text(json.dumps(final_index, indent=2, default=str), encoding="utf-8")


def main() -> dict[str, Any]:
    enable_network = os.environ.get("DUMMY_PUBLIC_INTEGRATION_MODE") == "1"
    reports = generate_v28_report_bundle(enable_network=enable_network)
    paths = {name: _write_report(name, data) for name, data in reports.items()}

    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v28.json", final)
    paths["final_report_v28.json"] = final_path
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v28_required_commands"] = _required_test_commands()
    tests_summary["v28_required_tests"] = _required_v28_tests()
    tests_summary["v28_required_reports"] = _v28_report_names(reports)
    tests_summary["v28_report_generated_at"] = final["generated_at"]
    tests_summary["v28_final_verdict"] = final["verdict"]
    tests_summary["v28_required_test_count"] = len(tests_summary["v28_required_tests"])
    tests_summary["v28_required_report_count"] = len(tests_summary["v28_required_reports"])
    _write_report("tests_summary.json", tests_summary)

    return final


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
