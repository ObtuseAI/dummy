"""Generate DUMMY V21 source activation breakout reports."""

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

from predator_mesh.v21 import MILESTONE
from predator_mesh.v21.reports import V21ReportFactory


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _v21_core_report_names() -> list[str]:
    return [
        "source_activation_policy_report_v1.json",
        "official_public_auto_approval_policy_report_v1.json",
        "key_required_source_policy_report_v1.json",
        "licensed_commercial_source_policy_report_v1.json",
        "sports_terms_strict_policy_report_v1.json",
        "source_approval_cockpit_report_v1.json",
        "source_approval_queue_report_v1.json",
        "source_approval_operator_packet_v1.json",
        "source_allowlist_delta_recommendation_v1.json",
        "official_public_real_feed_activator_report_v1.json",
        "official_public_feed_health_report_v1.json",
        "official_public_evidence_packet_manifest_v1.json",
        "official_public_fallback_reason_report_v1.json",
        "eia_energy_real_adapter_v1_report.json",
        "eia_oil_inventory_evidence_report_v1.json",
        "eia_energy_evidence_packet_report_v1.json",
        "eia_energy_source_blocker_report_v1.json",
        "nws_weather_real_adapter_v1_report.json",
        "weather_official_evidence_packet_report_v1.json",
        "weather_official_source_blocker_report_v1.json",
        "oil_weather_disruption_evidence_report_v1.json",
        "crypto_exchange_native_public_readonly_plan_report_v1.json",
        "crypto_exchange_public_probe_report_v1.json",
        "crypto_orderbook_public_evidence_report_v1.json",
        "crypto_cross_exchange_divergence_evidence_report_v1.json",
        "crypto_exchange_source_blocker_report_v1.json",
        "finance_macro_official_activation_v1_report.json",
        "finance_macro_official_evidence_packet_report_v1.json",
        "macro_release_calendar_evidence_report_v1.json",
        "finance_official_source_blocker_report_v1.json",
        "nasdaq_direction_bootstrap_v1_report.json",
        "nasdaq_bootstrap_evidence_packet_report_v1.json",
        "nasdaq_tier0_blocker_report_v1.json",
        "nasdaq_forecast_readiness_gate_report_v1.json",
        "oil_direction_bootstrap_v1_report.json",
        "oil_bootstrap_evidence_packet_report_v1.json",
        "oil_tier0_blocker_report_v1.json",
        "oil_forecast_readiness_gate_report_v1.json",
        "licensed_market_data_acquisition_planner_report_v1.json",
        "vendor_capability_matrix_v1.json",
        "operator_acquisition_checklist_v1.json",
        "source_cost_benefit_score_report_v1.json",
        "github_miner_live_bounded_upgrade_report_v1.json",
        "github_live_search_probe_report_v1.json",
        "github_rate_limit_state_report_v1.json",
        "github_repo_adapter_prioritizer_report_v1.json",
        "evidence_router_v3_report.json",
        "evidence_role_report_v1.json",
        "evidence_sufficiency_v2_report.json",
        "evidence_route_truth_report_v1.json",
        "forecast_pipeline_v3_report.json",
        "forecast_evidence_sufficiency_gate_report_v1.json",
        "forecast_context_only_blocker_report_v1.json",
        "forecast_edge_terrain_requirement_report_v1.json",
        "compounding_control_plane_v4_report.json",
        "source_activation_work_queue_report_v1.json",
        "source_acquisition_work_queue_report_v1.json",
        "adapter_implementation_work_queue_report_v1.json",
        "edge_terrain_improvement_queue_report_v1.json",
        "domain_scoreboard_v5_report.json",
        "source_activation_breakout_scoreboard_v1.json",
        "edge_readiness_by_domain_report_v1.json",
        "dummy_mission_state_report_v7.json",
        "dashboard_v21_report_v1.json",
        "v21_runtime_budget_report_v1.json",
        "official_feed_call_budget_report_v1.json",
        "source_activation_call_limiter_report_v1.json",
        "github_live_search_call_limiter_report_v1.json",
        "dashboard_cache_policy_v3_report.json",
        "report_chain_runtime_profiler_v4_report.json",
    ]


def _v21_security_report_names() -> list[str]:
    return [
        "no_secret_leak_report_v21.json",
        "no_kalshi_private_key_leak_report_v21.json",
        "no_source_api_key_leak_report_v21.json",
        "no_github_token_leak_report_v21.json",
        "no_llm_secret_leak_report_v21.json",
        "no_direct_order_bypass_report_v21.json",
        "no_direct_cancel_bypass_report_v21.json",
        "no_live_submit_still_disabled_report_v21.json",
        "no_caps_config_modification_report_v21.json",
        "readonly_only_source_activation_report_v21.json",
        "no_unauthorized_source_report_v21.json",
        "no_questionable_odds_scraping_report_v21.json",
        "no_undocumented_sports_endpoint_activation_report_v21.json",
        "no_unapproved_source_activation_report_v21.json",
        "no_commercial_source_without_approval_report_v21.json",
        "no_fixture_claimed_real_report_v21.json",
        "no_context_claimed_edge_report_v21.json",
        "no_outcome_fabrication_report_v21.json",
        "no_github_repo_code_execution_report_v21.json",
        "blunder_separation_recheck_v21.json",
        "dummy_canonical_identity_report_v21.json",
    ]


def _v21_report_names() -> list[str]:
    return ["final_report.json", "tests_summary.json", "final_report_v21.json", *_v21_core_report_names(), *_v21_security_report_names()]


def _required_test_commands() -> list[str]:
    return [
        "python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60",
        "python -m pytest tests/ -q --tb=short --timeout=60",
        "cd dashboard/frontend && npm run build",
        *[f"python scripts/generate_v{suffix}_reports.py" for suffix in ["8", "8_1", "8_2", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21"]],
    ]


def _required_v21_tests() -> list[str]:
    return [
        "test_source_activation_policy.py",
        "test_official_public_auto_approval_policy.py",
        "test_key_required_source_policy.py",
        "test_licensed_commercial_source_policy.py",
        "test_sports_terms_strict_policy.py",
        "test_source_approval_cockpit.py",
        "test_source_approval_queue.py",
        "test_source_approval_operator_packet.py",
        "test_source_allowlist_delta_recommendation.py",
        "test_official_public_real_feed_activator.py",
        "test_official_public_feed_health.py",
        "test_official_public_evidence_packet_manifest.py",
        "test_official_public_fallback_reason.py",
        "test_eia_energy_real_adapter_v1.py",
        "test_eia_oil_inventory_evidence.py",
        "test_eia_energy_evidence_packet.py",
        "test_eia_energy_source_blocker.py",
        "test_nws_weather_real_adapter_v1.py",
        "test_weather_official_evidence_packet.py",
        "test_weather_official_source_blocker.py",
        "test_oil_weather_disruption_evidence.py",
        "test_crypto_exchange_native_public_readonly_plan.py",
        "test_crypto_exchange_public_probe.py",
        "test_crypto_orderbook_public_evidence.py",
        "test_crypto_cross_exchange_divergence_evidence.py",
        "test_crypto_exchange_source_blocker.py",
        "test_finance_macro_official_activation_v1.py",
        "test_finance_macro_official_evidence_packet.py",
        "test_macro_release_calendar_evidence.py",
        "test_finance_official_source_blocker.py",
        "test_nasdaq_direction_bootstrap_v1.py",
        "test_nasdaq_bootstrap_evidence_packet.py",
        "test_nasdaq_tier0_blocker.py",
        "test_nasdaq_forecast_readiness_gate.py",
        "test_oil_direction_bootstrap_v1.py",
        "test_oil_bootstrap_evidence_packet.py",
        "test_oil_tier0_blocker.py",
        "test_oil_forecast_readiness_gate.py",
        "test_licensed_market_data_acquisition_planner.py",
        "test_vendor_capability_matrix.py",
        "test_operator_acquisition_checklist.py",
        "test_source_cost_benefit_score.py",
        "test_github_miner_live_bounded_upgrade.py",
        "test_github_live_search_probe.py",
        "test_github_rate_limit_state.py",
        "test_github_repo_adapter_prioritizer.py",
        "test_evidence_router_v3.py",
        "test_evidence_role.py",
        "test_evidence_sufficiency_v2.py",
        "test_evidence_route_truth.py",
        "test_forecast_pipeline_v3.py",
        "test_forecast_evidence_sufficiency_gate.py",
        "test_forecast_context_only_blocker.py",
        "test_forecast_edge_terrain_requirement.py",
        "test_compounding_control_plane_v4.py",
        "test_source_activation_work_queue.py",
        "test_source_acquisition_work_queue.py",
        "test_adapter_implementation_work_queue.py",
        "test_edge_terrain_improvement_queue.py",
        "test_domain_scoreboard_v5.py",
        "test_source_activation_breakout_scoreboard.py",
        "test_edge_readiness_by_domain.py",
        "test_dummy_mission_state_v21.py",
        "test_dashboard_v21.py",
        "test_v21_runtime_budget.py",
        "test_official_feed_call_budget.py",
        "test_source_activation_call_limiter.py",
        "test_github_live_search_call_limiter.py",
        "test_dashboard_cache_policy_v3.py",
        "test_report_chain_runtime_profiler_v4.py",
        "test_no_secret_leak_v21.py",
        "test_no_kalshi_private_key_leak_v21.py",
        "test_no_source_api_key_leak_v21.py",
        "test_no_github_token_leak_v21.py",
        "test_no_llm_secret_leak_v21.py",
        "test_no_direct_order_bypass_v21.py",
        "test_no_direct_cancel_bypass_v21.py",
        "test_no_live_submit_still_disabled_v21.py",
        "test_no_caps_config_modification_v21.py",
        "test_readonly_only_source_activation_v21.py",
        "test_no_unauthorized_source_v21.py",
        "test_no_questionable_odds_scraping_v21.py",
        "test_no_undocumented_sports_endpoint_activation_v21.py",
        "test_no_unapproved_source_activation_v21.py",
        "test_no_commercial_source_without_approval_v21.py",
        "test_no_fixture_claimed_real_v21.py",
        "test_no_context_claimed_edge_v21.py",
        "test_no_outcome_fabrication_v21.py",
        "test_no_github_repo_code_execution_v21.py",
        "test_blunder_separation_v21.py",
        "test_dummy_canonical_identity_v21.py",
        "test_timeout_guards_still_intact_v21.py",
        "test_v17_truth_loop_still_passes_v21.py",
        "test_v18_domain_foundation_still_passes_or_partial_expected_v21.py",
        "test_v19_activation_architecture_still_passes_or_partial_expected_v21.py",
        "test_v20_source_universe_still_passes_or_partial_expected_v21.py",
    ]


def generate_v21_report_bundle(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    return V21ReportFactory(enable_network=enable_network).build()


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    from archive.report_scripts.caps_integrity import reconcile_v17_truth_loop_evidence

    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v7.json"]
    activation = reports["official_public_real_feed_activator_report_v1.json"]
    real_split = mission["real_vs_fixture_split"]
    final_verdict = "FAIL" if failures else "PASS" if real_split["real_read_only"] > 0 else "PARTIAL"
    final_v17 = _load_report("final_report_v17.json", {})
    final_v18 = _load_report("final_report_v18.json", {})
    final_v19 = _load_report("final_report_v19.json", {})
    final_v20 = _load_report("final_report_v20.json", {})
    v17_evidence = reconcile_v17_truth_loop_evidence(final_v17)
    report_paths = {name: str(paths.get(name, ARTIFACTS / name)) for name in reports}
    return {
        "generated_at": now_iso(),
        "workstream": "V21: Final Source Activation Breakout",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "partial_reason": "" if final_verdict == "PASS" else "V21 policy, cockpit, activation, bootstrap, planner, router, forecast, dashboard, and safety surfaces are in place; real activation remains blocked where sources are unavailable, disabled in deterministic path, key/license-gated, terms-gated, or approval-gated.",
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": report_paths,
        "failures": failures,
        "partials": partials,
        "v17_truth_loop_status": v17_evidence["historical_truth_loop_status"],
        "v17_truth_loop_status_scope": v17_evidence["historical_truth_loop_scope"],
        "v17_archived_aggregate_status": v17_evidence["archived_aggregate_verdict"],
        "v17_current_runtime_caps_status": v17_evidence["current_runtime_caps_status"],
        "v17_retroactive_caps_failure_reconciled": v17_evidence["retroactive_caps_failure_reconciled"],
        "v18_domain_foundation_status": final_v18.get("verdict", mission["v18_domain_foundation_status"]),
        "v19_activation_architecture_status": final_v19.get("verdict", mission["v19_activation_architecture_status"]),
        "v20_source_universe_status": final_v20.get("verdict", mission["v20_source_universe_status"]),
        "live_submit_enabled": False,
        "caps_config_status": reports["no_caps_config_modification_report_v21.json"]["verdict"],
        "source_activation_policy_status": mission["source_activation_policy_status"],
        "source_approval_cockpit_status": mission["source_approval_cockpit_status"],
        "official_public_activation_status": mission["official_public_activation_status"],
        "activated_source_count": activation["activated_source_count"],
        "blocked_source_count": activation["blocked_source_count"],
        "eia_energy_status": mission["eia_energy_status"],
        "nws_noaa_weather_status": mission["nws_noaa_weather_status"],
        "crypto_public_exchange_status": mission["crypto_public_exchange_status"],
        "finance_macro_official_status": mission["finance_macro_official_status"],
        "nasdaq_bootstrap_status": mission["nasdaq_bootstrap_status"],
        "oil_bootstrap_status": mission["oil_bootstrap_status"],
        "licensed_acquisition_planner_status": mission["licensed_acquisition_planner_status"],
        "github_miner_mode": mission["github_miner_mode"],
        "evidence_router_v3_status": mission["evidence_router_v3_status"],
        "context_vs_edge_split": mission["context_vs_edge_split"],
        "forecast_pipeline_v3_status": mission["forecast_pipeline_v3_status"],
        "forecast_ledger_write_counts": mission["forecast_ledger_write_counts"],
        "compounding_control_plane_v4_status": mission["compounding_control_plane_v4_status"],
        "top_acquisition_recommendations": mission["top_acquisition_recommendations"],
        "domain_scoreboard_v5_status": mission["domain_scoreboard_v5_status"],
        "real_vs_fixture_split": real_split,
        "no_secret_leak_status": reports["no_secret_leak_report_v21.json"]["verdict"],
        "no_source_api_key_leak_status": reports["no_source_api_key_leak_report_v21.json"]["verdict"],
        "no_github_token_leak_status": reports["no_github_token_leak_report_v21.json"]["verdict"],
        "no_kalshi_private_key_leak_status": reports["no_kalshi_private_key_leak_report_v21.json"]["verdict"],
        "no_direct_order_bypass_status": reports["no_direct_order_bypass_report_v21.json"]["verdict"],
        "no_direct_cancel_bypass_status": reports["no_direct_cancel_bypass_report_v21.json"]["verdict"],
        "no_unauthorized_source_status": reports["no_unauthorized_source_report_v21.json"]["verdict"],
        "no_questionable_odds_scraping_status": reports["no_questionable_odds_scraping_report_v21.json"]["verdict"],
        "no_unapproved_source_activation_status": reports["no_unapproved_source_activation_report_v21.json"]["verdict"],
        "no_commercial_source_without_approval_status": reports["no_commercial_source_without_approval_report_v21.json"]["verdict"],
        "no_fixture_claimed_real_status": reports["no_fixture_claimed_real_report_v21.json"]["verdict"],
        "no_context_claimed_edge_status": reports["no_context_claimed_edge_report_v21.json"]["verdict"],
        "no_outcome_fabrication_status": reports["no_outcome_fabrication_report_v21.json"]["verdict"],
        "no_github_repo_code_execution_status": reports["no_github_repo_code_execution_report_v21.json"]["verdict"],
        "blunder_separation_status": reports["blunder_separation_recheck_v21.json"]["verdict"],
        "dashboard_status": reports["dashboard_v21_report_v1.json"]["verdict"],
        "proof_paths": {
            "final_report_v21": str(ARTIFACTS / "final_report_v21.json"),
            "final_report": str(ARTIFACTS / "final_report.json"),
            "tests_summary": str(ARTIFACTS / "tests_summary.json"),
        },
        "remaining_operator_actions": mission["top_blockers"],
        "secret_values_exposed": False,
    }


def generate_all_v21_reports_for_tests(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    reports = generate_v21_report_bundle(enable_network=enable_network)
    reports["final_report_v21.json"] = _build_final(reports)
    return reports


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = dict(final)
    final_index["final_report_v21"] = str(final_path)
    final_index["v21"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v21": str(final_path),
        "partial_reason": final["partial_reason"],
    }
    existing = _load_report("final_report.json", {})
    if existing:
        final_index["previous_final_report_snapshot"] = {key: existing[key] for key in ("generated_at", "milestone", "verdict", "partial_reason") if key in existing}
        for key, value in existing.items():
            if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
                final_index[key] = value
    (ARTIFACTS / "final_report.json").write_text(json.dumps(final_index, indent=2, default=str), encoding="utf-8")


def main() -> dict[str, Any]:
    enable_network = os.environ.get("DUMMY_V21_ENABLE_NETWORK", "1") != "0"
    reports = generate_v21_report_bundle(enable_network=enable_network)
    paths = {name: _write_report(name, data) for name, data in reports.items()}

    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v21.json", final)
    paths["final_report_v21.json"] = final_path
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v21_required_commands"] = _required_test_commands()
    tests_summary["v21_required_tests"] = _required_v21_tests()
    tests_summary["v21_required_reports"] = _v21_report_names()
    tests_summary["v21_report_generated_at"] = final["generated_at"]
    tests_summary["v21_final_verdict"] = final["verdict"]
    (ARTIFACTS / "tests_summary.json").write_text(json.dumps(tests_summary, indent=2, default=str), encoding="utf-8")

    print(json.dumps(final, indent=2, default=str))
    return final


if __name__ == "__main__":
    main()

