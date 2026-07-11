"""Generate DUMMY V24 open-source/public-data edge bootstrap reports."""

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

from predator_mesh.v24 import MILESTONE
from predator_mesh.v24.reports import V24ReportFactory


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


def generate_v24_report_bundle(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    return V24ReportFactory(enable_network=enable_network).build()


def _required_test_commands() -> list[str]:
    return [
        "python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60",
        "python -m pytest tests/ -q --tb=short --timeout=60",
        "cd dashboard/frontend && npm run build",
        *[
            f"python scripts/generate_v{suffix}_reports.py"
            for suffix in [
                "8",
                "8_1",
                "8_2",
                "9",
                "10",
                "11",
                "12",
                "13",
                "14",
                "15",
                "16",
                "17",
                "18",
                "19",
                "20",
                "21",
                "22",
                "23",
                "24",
            ]
        ],
    ]


def _required_v24_tests() -> list[str]:
    return [
        "test_open_source_source_doctrine_v1.py",
        "test_public_open_data_preference.py",
        "test_keyless_source_preference.py",
        "test_licensed_source_optionality_policy.py",
        "test_paid_feed_nonblocking_policy.py",
        "test_open_source_source_universe_reclassifier.py",
        "test_open_source_candidate_score.py",
        "test_open_data_candidate_score.py",
        "test_keyless_public_candidate_score.py",
        "test_commercial_optional_candidate_score.py",
        "test_source_progress_impact_class.py",
        "test_keyless_public_adapter_expansion_v1.py",
        "test_keyless_public_adapter_candidate.py",
        "test_keyless_public_probe.py",
        "test_keyless_public_evidence_packet.py",
        "test_keyless_public_activation_decision.py",
        "test_public_proxy_edge_terrain_v1.py",
        "test_public_proxy_evidence.py",
        "test_proxy_edge_class.py",
        "test_proxy_edge_confidence.py",
        "test_proxy_overclaim_guard.py",
        "test_proxy_no_trade_gate.py",
        "test_nasdaq_open_proxy_terrain_v1.py",
        "test_nasdaq_public_proxy_need.py",
        "test_nasdaq_public_proxy_evidence.py",
        "test_nasdaq_open_proxy_readiness.py",
        "test_nasdaq_open_proxy_no_trade_gate.py",
        "test_oil_open_proxy_terrain_v1.py",
        "test_oil_public_proxy_need.py",
        "test_oil_public_proxy_evidence.py",
        "test_oil_open_proxy_readiness.py",
        "test_oil_open_proxy_no_trade_gate.py",
        "test_open_data_replay_dataset_builder_v1.py",
        "test_replay_dataset_source.py",
        "test_replay_dataset_provenance.py",
        "test_replay_dataset_license_class.py",
        "test_replay_dataset_integrity_check.py",
        "test_replay_dataset_limitations.py",
        "test_replay_calibration_harness_v2.py",
        "test_replay_scenario_generator.py",
        "test_replay_forecast_policy.py",
        "test_replay_no_trade_policy.py",
        "test_replay_calibration_sample.py",
        "test_replay_calibration_guard.py",
        "test_open_source_baseline_lab_v1.py",
        "test_baseline_strategy_registry.py",
        "test_baseline_strategy_candidate.py",
        "test_baseline_backtest_replay_result.py",
        "test_baseline_promotion_guard.py",
        "test_keyless_live_forecast_expansion_v2.py",
        "test_keyless_forecast_candidate.py",
        "test_keyless_forecast_decision.py",
        "test_keyless_forecast_ledger_write.py",
        "test_keyless_forecast_observer_plan.py",
        "test_open_source_adapter_work_queue_v1.py",
        "test_open_source_adapter_candidate.py",
        "test_open_source_adapter_license_review.py",
        "test_open_source_adapter_implementation_sketch.py",
        "test_open_source_adapter_test_plan.py",
        "test_open_source_adapter_no_exec_guard.py",
        "test_optional_premium_feed_demotion_v1.py",
        "test_premium_feed_optional_status.py",
        "test_premium_feed_upgrade_value.py",
        "test_premium_feed_nonblocking_proof.py",
        "test_premium_feed_operator_note.py",
        "test_open_source_source_truth_score_v6.py",
        "test_open_data_truth_state.py",
        "test_keyless_public_truth_state.py",
        "test_replay_truth_state.py",
        "test_proxy_truth_state.py",
        "test_premium_optional_truth_state.py",
        "test_source_truth_overclaim_guard_v6.py",
        "test_forecast_lifecycle_ledger_v3.py",
        "test_forecast_source_mode_label.py",
        "test_forecast_proxy_label.py",
        "test_forecast_replay_label.py",
        "test_forecast_lifecycle_mode_separation_proof.py",
        "test_open_source_compounding_control_plane_v8.py",
        "test_open_source_acceleration_work_queue.py",
        "test_keyless_public_expansion_queue.py",
        "test_replay_calibration_expansion_queue.py",
        "test_proxy_terrain_improvement_queue.py",
        "test_optional_premium_upgrade_queue.py",
        "test_next_bundle_recommendation_v24_open_source.py",
        "test_domain_scoreboard_v9.py",
        "test_open_source_progress_scoreboard.py",
        "test_keyless_public_source_scoreboard.py",
        "test_replay_proxy_scoreboard.py",
        "test_optional_premium_scoreboard.py",
        "test_dummy_mission_state_v24.py",
        "test_dashboard_v24.py",
        "test_v24_runtime_budget.py",
        "test_keyless_public_probe_budget.py",
        "test_open_data_replay_runtime_guard.py",
        "test_open_source_adapter_work_queue_guard.py",
        "test_dashboard_cache_policy_v6.py",
        "test_report_chain_runtime_profiler_v7.py",
        "test_no_secret_leak_v24.py",
        "test_no_kalshi_private_key_leak_v24.py",
        "test_no_source_api_key_leak_v24.py",
        "test_no_github_token_leak_v24.py",
        "test_no_llm_secret_leak_v24.py",
        "test_no_direct_order_bypass_v24.py",
        "test_no_direct_cancel_bypass_v24.py",
        "test_no_live_submit_still_disabled_v24.py",
        "test_no_caps_config_modification_v24.py",
        "test_readonly_only_source_activation_v24.py",
        "test_no_unauthorized_source_v24.py",
        "test_no_questionable_odds_scraping_v24.py",
        "test_no_unapproved_source_activation_v24.py",
        "test_no_commercial_source_without_approval_v24.py",
        "test_no_premium_feed_required_global_blocker_v24.py",
        "test_no_fixture_claimed_real_v24.py",
        "test_no_replay_claimed_live_v24.py",
        "test_no_replay_score_claimed_live_v24.py",
        "test_no_proxy_claimed_exchange_native_v24.py",
        "test_no_context_claimed_edge_v24.py",
        "test_no_outcome_fabrication_v24.py",
        "test_no_github_repo_code_execution_v24.py",
        "test_no_replay_scoring_to_execution_bridge_v24.py",
        "test_no_keyless_forecast_to_execution_bridge_v24.py",
        "test_no_calibration_to_execution_bridge_v24.py",
        "test_no_source_gate_to_execution_bridge_v24.py",
        "test_no_adapter_probe_to_execution_bridge_v24.py",
        "test_blunder_separation_v24.py",
        "test_dummy_canonical_identity_v24.py",
        "test_timeout_guards_still_intact_v24.py",
        "test_v17_truth_loop_still_passes_v24.py",
        "test_v21_source_activation_still_passes_v24.py",
        "test_v22_forecast_write_breakthrough_still_passes_v24.py",
        "test_v23_observer_calibration_still_passes_or_partial_expected_v24.py",
    ]


def _v24_report_names(reports: dict[str, dict[str, Any]] | None = None) -> list[str]:
    names = sorted((reports or generate_v24_report_bundle(enable_network=False)).keys())
    return ["final_report.json", "tests_summary.json", "final_report_v24.json", *names]


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v10.json"]
    final_v17 = _load_report("final_report_v17.json", {})
    final_v21 = _load_report("final_report_v21.json", {})
    final_v22 = _load_report("final_report_v22.json", {})
    final_v23 = _load_report("final_report_v23.json", {})
    final_verdict = "FAIL" if failures else "PARTIAL" if partials else "PASS"
    report_paths = {name: str(paths.get(name, ARTIFACTS / name)) for name in reports}
    return {
        "generated_at": now_iso(),
        "workstream": "V24: Open-Source Public Data Edge Bootstrap",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "partial_reason": "" if final_verdict == "PASS" else "Live forecasts remain unresolved/not due, live scored count is 0, and Nasdaq/oil remain honest no-trade proxy states while replay samples are labeled replay/fixture-only.",
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": report_paths,
        "failures": failures,
        "partials": partials,
        "v17_truth_loop_status": final_v17.get("verdict", mission["v17_truth_loop_status"]),
        "v21_source_activation_status": final_v21.get("verdict", mission["v21_source_activation_status"]),
        "v22_forecast_write_status": final_v22.get("forecast_write_breakthrough_status", mission["v22_forecast_write_status"]),
        "v23_observer_calibration_status": final_v23.get("v22_forecast_observer_closure_status", mission["v23_observer_calibration_status"]),
        "live_submit_enabled": False,
        "live_submit_flag_status": "enabled=false",
        "caps_config_status": reports["no_caps_config_modification_report_v24.json"]["verdict"],
        "open_source_source_doctrine_status": reports["open_source_source_doctrine_v1_report.json"]["verdict"],
        "source_universe_reclassification_status": reports["open_source_source_universe_reclassifier_report_v1.json"]["reclassification_status"],
        "keyless_public_adapter_expansion_status": reports["keyless_public_adapter_expansion_v1_report.json"]["keyless_public_expansion_status"],
        "keyless_public_active_count": mission["keyless_public_active_count"],
        "public_proxy_terrain_status": reports["public_proxy_edge_terrain_v1_report.json"]["public_proxy_terrain_status"],
        "nasdaq_open_proxy_status": mission["nasdaq_open_proxy_status"],
        "oil_open_proxy_status": mission["oil_open_proxy_status"],
        "open_data_replay_dataset_status": reports["open_data_replay_dataset_builder_v1_report.json"]["open_data_replay_dataset_status"],
        "replay_forecast_count": mission["replay_forecast_count"],
        "replay_scored_count": mission["replay_scored_count"],
        "replay_score_count": mission["replay_score_count"],
        "open_source_baseline_lab_status": reports["open_source_baseline_lab_v1_report.json"]["open_source_baseline_lab_status"],
        "keyless_live_forecast_expansion_status": reports["keyless_live_forecast_expansion_v2_report.json"]["keyless_live_forecast_expansion_status"],
        "live_forecast_count": mission["live_forecast_count"],
        "live_unresolved_count": mission["live_unresolved_count"],
        "live_scored_count": mission["live_scored_count"],
        "open_source_adapter_work_queue_status": reports["open_source_adapter_work_queue_v1_report.json"]["open_source_adapter_work_queue_status"],
        "optional_premium_feed_demotion_status": reports["optional_premium_feed_demotion_v1_report.json"]["optional_premium_demotion_status"],
        "premium_optional_blocker_count": mission["optional_premium_blocker_count"],
        "source_truth_v6_status": reports["open_source_source_truth_score_v6_report.json"]["source_truth_v6_status"],
        "forecast_lifecycle_ledger_v3_status": reports["forecast_lifecycle_ledger_v3_report.json"]["forecast_lifecycle_ledger_v3_status"],
        "open_source_compounding_v8_status": reports["open_source_compounding_control_plane_v8_report.json"]["open_source_compounding_v8_status"],
        "next_open_source_bundle_recommendation": reports["next_bundle_recommendation_v24_open_source_report.json"]["recommendation"],
        "domain_scoreboard_v9_status": reports["domain_scoreboard_v9_report.json"]["domain_scoreboard_v9_status"],
        "mission_state_verdict": mission["verdict"],
        "no_secret_leak_status": reports["no_secret_leak_report_v24.json"]["verdict"],
        "no_source_api_key_leak_status": reports["no_source_api_key_leak_report_v24.json"]["verdict"],
        "no_github_token_leak_status": reports["no_github_token_leak_report_v24.json"]["verdict"],
        "no_kalshi_private_key_leak_status": reports["no_kalshi_private_key_leak_report_v24.json"]["verdict"],
        "no_direct_order_bypass_status": reports["no_direct_order_bypass_report_v24.json"]["verdict"],
        "no_direct_cancel_bypass_status": reports["no_direct_cancel_bypass_report_v24.json"]["verdict"],
        "no_unauthorized_source_status": reports["no_unauthorized_source_report_v24.json"]["verdict"],
        "no_questionable_odds_scraping_status": reports["no_questionable_odds_scraping_report_v24.json"]["verdict"],
        "no_unapproved_source_activation_status": reports["no_unapproved_source_activation_report_v24.json"]["verdict"],
        "no_commercial_source_without_approval_status": reports["no_commercial_source_without_approval_report_v24.json"]["verdict"],
        "no_premium_feed_required_global_blocker_status": reports["no_premium_feed_required_global_blocker_report_v24.json"]["verdict"],
        "no_fixture_claimed_real_status": reports["no_fixture_claimed_real_report_v24.json"]["verdict"],
        "no_replay_claimed_live_status": reports["no_replay_claimed_live_report_v24.json"]["verdict"],
        "no_replay_score_claimed_live_status": reports["no_replay_score_claimed_live_report_v24.json"]["verdict"],
        "no_proxy_claimed_exchange_native_status": reports["no_proxy_claimed_exchange_native_report_v24.json"]["verdict"],
        "no_context_claimed_edge_status": reports["no_context_claimed_edge_report_v24.json"]["verdict"],
        "no_outcome_fabrication_status": reports["no_outcome_fabrication_report_v24.json"]["verdict"],
        "no_replay_scoring_to_execution_bridge_status": reports["no_replay_scoring_to_execution_bridge_report_v24.json"]["verdict"],
        "no_keyless_forecast_to_execution_bridge_status": reports["no_keyless_forecast_to_execution_bridge_report_v24.json"]["verdict"],
        "no_calibration_to_execution_bridge_status": reports["no_calibration_to_execution_bridge_report_v24.json"]["verdict"],
        "no_source_gate_to_execution_bridge_status": reports["no_source_gate_to_execution_bridge_report_v24.json"]["verdict"],
        "no_adapter_probe_to_execution_bridge_status": reports["no_adapter_probe_to_execution_bridge_report_v24.json"]["verdict"],
        "blunder_separation_status": reports["blunder_separation_recheck_v24.json"]["verdict"],
        "dashboard_status": reports["dashboard_v24_report_v1.json"]["verdict"],
        "proof_paths": mission["proof_paths"],
        "remaining_operator_actions": [
            "Review optional premium feeds only for edge-specific upgrades after open/public evidence is exhausted.",
            "Increase replay sample size with public provenance before granting live source accuracy credit.",
            "Approve safe public equity/ETF and volatility proxies before raising Nasdaq confidence.",
            "Approve EIA keyless/keyed path if oil fundamentals need stronger evidence.",
        ],
    }


def generate_all_v24_reports_for_tests(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    reports = generate_v24_report_bundle(enable_network=enable_network)
    reports["final_report_v24.json"] = _build_final(reports)
    return reports


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = dict(final)
    final_index["final_report_v24"] = str(final_path)
    final_index["v24"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v24": str(final_path),
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
    enable_network = os.environ.get("DUMMY_V24_ENABLE_NETWORK", "0") == "1"
    reports = generate_v24_report_bundle(enable_network=enable_network)
    paths = {name: _write_report(name, data) for name, data in reports.items()}

    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v24.json", final)
    paths["final_report_v24.json"] = final_path
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v24_required_commands"] = _required_test_commands()
    tests_summary["v24_required_tests"] = _required_v24_tests()
    tests_summary["v24_required_reports"] = _v24_report_names(reports)
    tests_summary["v24_report_generated_at"] = final["generated_at"]
    tests_summary["v24_final_verdict"] = final["verdict"]
    (ARTIFACTS / "tests_summary.json").write_text(json.dumps(tests_summary, indent=2, default=str), encoding="utf-8")

    print(json.dumps(final, indent=2, default=str))
    return final


if __name__ == "__main__":
    main()
