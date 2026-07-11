"""Generate DUMMY V23 observer, calibration, and adapter-closure reports."""

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

from predator_mesh.v23 import MILESTONE
from predator_mesh.v23.reports import V23ReportFactory


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


def generate_v23_report_bundle(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    return V23ReportFactory(enable_network=enable_network).build()


def _required_test_commands() -> list[str]:
    return [
        "python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60",
        "python -m pytest tests/ -q --tb=short --timeout=60",
        "cd dashboard/frontend && npm run build",
        *[
            f"python scripts/generate_v{suffix}_reports.py"
            for suffix in ["8", "8_1", "8_2", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23"]
        ],
    ]


def _required_v23_tests() -> list[str]:
    return [
        "test_v22_forecast_observer_closure.py",
        "test_forecast_observation_attempt.py",
        "test_forecast_observation_decision.py",
        "test_forecast_observation_blocker.py",
        "test_crypto_forecast_outcome_observer_v1.py",
        "test_crypto_spot_settlement_probe.py",
        "test_crypto_forecast_outcome_status.py",
        "test_crypto_forecast_settlement_blocker.py",
        "test_weather_forecast_outcome_observer_v1.py",
        "test_weather_station_settlement_probe.py",
        "test_weather_forecast_outcome_status.py",
        "test_weather_forecast_settlement_blocker.py",
        "test_forecast_scoring_engine_v2.py",
        "test_forecast_score_candidate.py",
        "test_forecast_score_result.py",
        "test_forecast_score_blocker.py",
        "test_forecast_score_integrity_proof.py",
        "test_calibration_update_engine_v3.py",
        "test_domain_calibration_update.py",
        "test_calibration_bucket_update.py",
        "test_low_sample_calibration_warning.py",
        "test_calibration_queue_state.py",
        "test_forecast_attribution_engine_v2.py",
        "test_edge_forecast_attribution.py",
        "test_source_attribution_update.py",
        "test_no_trade_attribution_v2.py",
        "test_outcome_pending_attribution.py",
        "test_source_truth_score_v4.py",
        "test_source_truth_update.py",
        "test_edge_source_reliability_state.py",
        "test_context_source_reliability_state.py",
        "test_source_truth_promotion_gate.py",
        "test_tier0_adapter_closure_planner.py",
        "test_tier0_adapter_closure_candidate.py",
        "test_tier0_adapter_closure_status.py",
        "test_tier0_adapter_proof_requirement.py",
        "test_tier0_adapter_operator_action.py",
        "test_cme_readonly_adapter_gate_v1.py",
        "test_cme_futures_source_requirement.py",
        "test_cme_credential_presence_check.py",
        "test_cme_readonly_probe_plan.py",
        "test_cme_adapter_blocker.py",
        "test_databento_readonly_adapter_gate_v1.py",
        "test_databento_dataset_requirement.py",
        "test_databento_credential_presence_check.py",
        "test_databento_readonly_probe_plan.py",
        "test_databento_adapter_blocker.py",
        "test_eia_adapter_activation_closure_v2.py",
        "test_eia_key_presence_check.py",
        "test_eia_dataset_probe_plan_v2.py",
        "test_eia_inventory_series_mapper.py",
        "test_eia_oil_fundamental_evidence_gate.py",
        "test_eia_activation_blocker_v2.py",
        "test_rates_dxy_public_context_adapter_v1.py",
        "test_treasury_yield_evidence_v1.py",
        "test_dxy_proxy_evidence_v1.py",
        "test_rates_freshness_gate.py",
        "test_rates_dxy_context_guard.py",
        "test_nasdaq_edge_readiness_v2.py",
        "test_oil_edge_readiness_v2.py",
        "test_nasdaq_evidence_gap_state_v2.py",
        "test_oil_evidence_gap_state_v2.py",
        "test_directional_forecast_readiness_decision_v2.py",
        "test_forecast_lifecycle_ledger_v1.py",
        "test_forecast_lifecycle_record.py",
        "test_forecast_lifecycle_transition.py",
        "test_forecast_lifecycle_integrity_check.py",
        "test_compounding_control_plane_v6.py",
        "test_observer_follow_through_work_queue.py",
        "test_calibration_work_queue_v2.py",
        "test_tier0_closure_work_queue.py",
        "test_adapter_activation_work_queue_v2.py",
        "test_next_bundle_recommendation_v23.py",
        "test_domain_scoreboard_v7.py",
        "test_observer_calibration_scoreboard.py",
        "test_tier0_adapter_closure_scoreboard.py",
        "test_source_truth_scoreboard_v4.py",
        "test_dummy_mission_state_v23.py",
        "test_dashboard_v23.py",
        "test_v23_runtime_budget.py",
        "test_observer_call_budget.py",
        "test_forecast_scoring_runtime_guard.py",
        "test_tier0_adapter_probe_call_limiter.py",
        "test_dashboard_cache_policy_v5.py",
        "test_report_chain_runtime_profiler_v6.py",
        "test_no_secret_leak_v23.py",
        "test_no_kalshi_private_key_leak_v23.py",
        "test_no_source_api_key_leak_v23.py",
        "test_no_github_token_leak_v23.py",
        "test_no_llm_secret_leak_v23.py",
        "test_no_direct_order_bypass_v23.py",
        "test_no_direct_cancel_bypass_v23.py",
        "test_no_live_submit_still_disabled_v23.py",
        "test_no_caps_config_modification_v23.py",
        "test_readonly_only_source_activation_v23.py",
        "test_no_unauthorized_source_v23.py",
        "test_no_questionable_odds_scraping_v23.py",
        "test_no_unapproved_source_activation_v23.py",
        "test_no_commercial_source_without_approval_v23.py",
        "test_no_fixture_claimed_real_v23.py",
        "test_no_context_claimed_edge_v23.py",
        "test_no_outcome_fabrication_v23.py",
        "test_no_github_repo_code_execution_v23.py",
        "test_no_forecast_scoring_to_execution_bridge_v23.py",
        "test_no_observer_to_execution_bridge_v23.py",
        "test_no_calibration_to_execution_bridge_v23.py",
        "test_no_adapter_probe_to_execution_bridge_v23.py",
        "test_blunder_separation_v23.py",
        "test_dummy_canonical_identity_v23.py",
        "test_timeout_guards_still_intact_v23.py",
        "test_v17_truth_loop_still_passes_v23.py",
        "test_v21_source_activation_still_passes_v23.py",
        "test_v22_forecast_write_breakthrough_still_passes_v23.py",
    ]


def _v23_report_names(reports: dict[str, dict[str, Any]] | None = None) -> list[str]:
    names = sorted((reports or generate_v23_report_bundle(enable_network=False)).keys())
    return ["final_report.json", "tests_summary.json", "final_report_v23.json", *names]


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v9.json"]
    scoring = reports["forecast_scoring_engine_v2_report.json"]
    calibration = reports["calibration_update_engine_v3_report.json"]
    tier0 = reports["tier0_adapter_closure_planner_report_v1.json"]
    final_v17 = _load_report("final_report_v17.json", {})
    final_v21 = _load_report("final_report_v21.json", {})
    final_v22 = _load_report("final_report_v22.json", {})
    final_verdict = "FAIL" if failures else "PARTIAL" if partials else "PASS"
    report_paths = {name: str(paths.get(name, ARTIFACTS / name)) for name in reports}
    return {
        "generated_at": now_iso(),
        "workstream": "V23: Final Observer Calibration Tier-0 Adapter Closure",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "partial_reason": "" if final_verdict == "PASS" else "Forecast outcomes are not due yet and licensed/keyed sources remain blocked behind explicit operator gates.",
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": report_paths,
        "failures": failures,
        "partials": partials,
        "v17_truth_loop_status": final_v17.get("verdict", mission["v17_truth_loop_status"]),
        "v21_source_activation_status": final_v21.get("verdict", mission["v21_source_activation_status"]),
        "v22_forecast_write_status": final_v22.get("forecast_write_breakthrough_status", mission["v22_forecast_write_status"]),
        "live_submit_enabled": False,
        "live_submit_flag_status": "enabled=false",
        "caps_config_status": reports["no_caps_config_modification_report_v23.json"]["verdict"],
        "v22_forecast_observer_closure_status": reports["v22_forecast_observer_closure_report_v1.json"]["verdict"],
        "crypto_outcome_observer_status": reports["crypto_forecast_outcome_observer_v1_report.json"]["verdict"],
        "weather_outcome_observer_status": reports["weather_forecast_outcome_observer_v1_report.json"]["verdict"],
        "forecast_scoring_status": scoring["verdict"],
        "scored_forecast_count": scoring["scored_forecast_count"],
        "unresolved_forecast_count": scoring["unresolved_forecast_count"],
        "calibration_update_status": calibration["verdict"],
        "calibration_sample_count": calibration["calibration_sample_count"],
        "attribution_status": reports["forecast_attribution_engine_v2_report.json"]["verdict"],
        "source_truth_score_v4_status": reports["source_truth_score_v4_report.json"]["verdict"],
        "tier0_adapter_closure_planner_status": tier0["verdict"],
        "cme_adapter_gate_status": reports["cme_readonly_adapter_gate_v1_report.json"]["status"],
        "databento_adapter_gate_status": reports["databento_readonly_adapter_gate_v1_report.json"]["status"],
        "eia_adapter_activation_closure_status": reports["eia_adapter_activation_closure_v2_report.json"]["status"],
        "rates_dxy_context_status": reports["rates_dxy_public_context_adapter_v1_report.json"]["verdict"],
        "nasdaq_edge_readiness_status": reports["nasdaq_edge_readiness_v2_report.json"]["readiness"],
        "oil_edge_readiness_status": reports["oil_edge_readiness_v2_report.json"]["readiness"],
        "forecast_lifecycle_ledger_status": reports["forecast_lifecycle_ledger_v1_report.json"]["verdict"],
        "compounding_control_plane_v6_status": reports["compounding_control_plane_v6_report.json"]["verdict"],
        "next_bundle_recommendation": reports["next_bundle_recommendation_v23_report.json"]["recommendation"],
        "domain_scoreboard_v7_status": reports["domain_scoreboard_v7_report.json"]["verdict"],
        "mission_state_verdict": mission["verdict"],
        "no_secret_leak_status": reports["no_secret_leak_report_v23.json"]["verdict"],
        "no_source_api_key_leak_status": reports["no_source_api_key_leak_report_v23.json"]["verdict"],
        "no_github_token_leak_status": reports["no_github_token_leak_report_v23.json"]["verdict"],
        "no_kalshi_private_key_leak_status": reports["no_kalshi_private_key_leak_report_v23.json"]["verdict"],
        "no_direct_order_bypass_status": reports["no_direct_order_bypass_report_v23.json"]["verdict"],
        "no_direct_cancel_bypass_status": reports["no_direct_cancel_bypass_report_v23.json"]["verdict"],
        "no_unauthorized_source_status": reports["no_unauthorized_source_report_v23.json"]["verdict"],
        "no_questionable_odds_scraping_status": reports["no_questionable_odds_scraping_report_v23.json"]["verdict"],
        "no_unapproved_source_activation_status": reports["no_unapproved_source_activation_report_v23.json"]["verdict"],
        "no_commercial_source_without_approval_status": reports["no_commercial_source_without_approval_report_v23.json"]["verdict"],
        "no_fixture_claimed_real_status": reports["no_fixture_claimed_real_report_v23.json"]["verdict"],
        "no_context_claimed_edge_status": reports["no_context_claimed_edge_report_v23.json"]["verdict"],
        "no_outcome_fabrication_status": reports["no_outcome_fabrication_report_v23.json"]["verdict"],
        "no_forecast_scoring_to_execution_bridge_status": reports["no_forecast_scoring_to_execution_bridge_report_v23.json"]["verdict"],
        "no_observer_to_execution_bridge_status": reports["no_observer_to_execution_bridge_report_v23.json"]["verdict"],
        "no_calibration_to_execution_bridge_status": reports["no_calibration_to_execution_bridge_report_v23.json"]["verdict"],
        "no_adapter_probe_to_execution_bridge_status": reports["no_adapter_probe_to_execution_bridge_report_v23.json"]["verdict"],
        "blunder_separation_status": reports["blunder_separation_recheck_v23.json"]["verdict"],
        "dashboard_status": reports["dashboard_v23_report_v1.json"]["verdict"],
        "proof_paths": {
            "final_report_v23": str(ARTIFACTS / "final_report_v23.json"),
            "final_report": str(ARTIFACTS / "final_report.json"),
            "tests_summary": str(ARTIFACTS / "tests_summary.json"),
            "forecast_observer_closure": str(ARTIFACTS / "v22_forecast_observer_closure_report_v1.json"),
            "forecast_scoring": str(ARTIFACTS / "forecast_scoring_engine_v2_report.json"),
            "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v9.json"),
        },
        "remaining_operator_actions": [
            action["action"]
            for action in reports["tier0_adapter_operator_action_report_v1.json"]["actions"]
        ],
    }


def generate_all_v23_reports_for_tests(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    reports = generate_v23_report_bundle(enable_network=enable_network)
    reports["final_report_v23.json"] = _build_final(reports)
    return reports


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = dict(final)
    final_index["final_report_v23"] = str(final_path)
    final_index["v23"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v23": str(final_path),
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
    enable_network = os.environ.get("DUMMY_V23_ENABLE_NETWORK", "0") == "1"
    reports = generate_v23_report_bundle(enable_network=enable_network)
    paths = {name: _write_report(name, data) for name, data in reports.items()}

    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v23.json", final)
    paths["final_report_v23.json"] = final_path
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v23_required_commands"] = _required_test_commands()
    tests_summary["v23_required_tests"] = _required_v23_tests()
    tests_summary["v23_required_reports"] = _v23_report_names(reports)
    tests_summary["v23_report_generated_at"] = final["generated_at"]
    tests_summary["v23_final_verdict"] = final["verdict"]
    (ARTIFACTS / "tests_summary.json").write_text(json.dumps(tests_summary, indent=2, default=str), encoding="utf-8")

    print(json.dumps(final, indent=2, default=str))
    return final


if __name__ == "__main__":
    main()
