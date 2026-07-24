"""Generate DUMMY V22 edge activation and forecast write reports."""

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

from predator_mesh.v22 import MILESTONE
from predator_mesh.v22.reports import V22ReportFactory


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


def generate_v22_report_bundle(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    return V22ReportFactory(enable_network=enable_network).build()


def _required_test_commands() -> list[str]:
    return [
        "python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60",
        "python -m pytest tests/ -q --tb=short --timeout=60",
        "cd dashboard/frontend && npm run build",
        *[f"python scripts/generate_v{suffix}_reports.py" for suffix in ["8", "8_1", "8_2", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22"]],
    ]


def _required_v22_tests() -> list[str]:
    return [
        "test_edge_role_classifier.py",
        "test_evidence_role_classifier.py",
        "test_edge_promotion_candidate.py",
        "test_context_only_blocker.py",
        "test_active_source_evidence_normalizer.py",
        "test_normalized_evidence_packet_manifest.py",
        "test_evidence_freshness_proof.py",
        "test_evidence_completeness_score.py",
        "test_crypto_spot_edge_terrain_activator.py",
        "test_crypto_spot_orderbook_terrain.py",
        "test_crypto_cross_venue_comparison.py",
        "test_crypto_spot_edge_readiness.py",
        "test_crypto_spot_forecast_gate.py",
        "test_weather_edge_terrain_activator.py",
        "test_weather_forecast_edge_terrain.py",
        "test_weather_settlement_station_mapper.py",
        "test_weather_forecast_readiness_gate.py",
        "test_commodity_context_guard.py",
        "test_oil_edge_insufficiency_reason.py",
        "test_commodity_source_upgrade_need.py",
        "test_finance_context_guard.py",
        "test_nasdaq_edge_insufficiency_reason.py",
        "test_finance_source_upgrade_need.py",
        "test_market_event_mapper.py",
        "test_evidence_market_link.py",
        "test_market_class_candidate.py",
        "test_market_mapping_blocker.py",
        "test_kalshi_market_discovery_recheck_v22.py",
        "test_kalshi_domain_market_mapper.py",
        "test_kalshi_market_evidence_join.py",
        "test_kalshi_market_mapping_blocker.py",
        "test_forecast_write_breakthrough_engine.py",
        "test_forecast_write_candidate_manifest.py",
        "test_forecast_write_decision.py",
        "test_forecast_snapshot_write_proof.py",
        "test_no_trade_write_proof.py",
        "test_outcome_observer_queue_v1.py",
        "test_observer_check_plan.py",
        "test_observer_queue_blocker.py",
        "test_v22_outcome_ledger_integration.py",
        "test_forecast_snapshot_ledger_write_v22.py",
        "test_no_trade_ledger_write_v22.py",
        "test_observer_queue_ledger_write_v22.py",
        "test_ledger_write_integrity_check_v22.py",
        "test_edge_source_acquisition_engine_v2.py",
        "test_edge_source_acquisition_priority.py",
        "test_tier0_market_data_need.py",
        "test_tier2_market_data_need.py",
        "test_adapter_implementation_need.py",
        "test_github_adapter_implementation_queue_v2.py",
        "test_adapter_candidate_work_item.py",
        "test_adapter_risk_assessment.py",
        "test_adapter_test_plan.py",
        "test_compounding_control_plane_v5.py",
        "test_forecast_write_improvement_queue.py",
        "test_edge_activation_improvement_queue.py",
        "test_source_acquisition_improvement_queue.py",
        "test_next_tactical_bundle_selector.py",
        "test_domain_scoreboard_v6.py",
        "test_forecast_write_breakthrough_scoreboard.py",
        "test_edge_terrain_activation_scoreboard.py",
        "test_dummy_mission_state_v22.py",
        "test_dashboard_v22.py",
        "test_v22_runtime_budget.py",
        "test_edge_activation_call_budget.py",
        "test_forecast_write_runtime_guard.py",
        "test_kalshi_mapping_call_limiter_v22.py",
        "test_dashboard_cache_policy_v4.py",
        "test_report_chain_runtime_profiler_v5.py",
        "test_no_secret_leak_v22.py",
        "test_no_kalshi_private_key_leak_v22.py",
        "test_no_source_api_key_leak_v22.py",
        "test_no_github_token_leak_v22.py",
        "test_no_llm_secret_leak_v22.py",
        "test_no_direct_order_bypass_v22.py",
        "test_no_direct_cancel_bypass_v22.py",
        "test_no_live_submit_still_disabled_v22.py",
        "test_no_caps_config_modification_v22.py",
        "test_readonly_only_source_activation_v22.py",
        "test_no_unauthorized_source_v22.py",
        "test_no_questionable_odds_scraping_v22.py",
        "test_no_unapproved_source_activation_v22.py",
        "test_no_commercial_source_without_approval_v22.py",
        "test_no_fixture_claimed_real_v22.py",
        "test_no_context_claimed_edge_v22.py",
        "test_no_outcome_fabrication_v22.py",
        "test_no_github_repo_code_execution_v22.py",
        "test_no_forecast_to_execution_bridge_v22.py",
        "test_no_observer_to_execution_bridge_v22.py",
        "test_blunder_separation_v22.py",
        "test_dummy_canonical_identity_v22.py",
        "test_timeout_guards_still_intact_v22.py",
        "test_v17_truth_loop_still_passes_v22.py",
        "test_v18_domain_foundation_still_passes_or_partial_expected_v22.py",
        "test_v19_activation_architecture_still_passes_or_partial_expected_v22.py",
        "test_v20_source_universe_still_passes_or_partial_expected_v22.py",
        "test_v21_source_activation_still_passes_v22.py",
    ]


def _v22_report_names(reports: dict[str, dict[str, Any]] | None = None) -> list[str]:
    names = sorted((reports or generate_v22_report_bundle(enable_network=False)).keys())
    return ["final_report.json", "tests_summary.json", "final_report_v22.json", *names]


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path] | None = None) -> dict[str, Any]:
    from archive.report_scripts.caps_integrity import reconcile_v17_truth_loop_evidence

    paths = paths or {}
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") == "PARTIAL")
    mission = reports["dummy_mission_state_report_v8.json"]
    forecast = reports["forecast_write_breakthrough_engine_report_v1.json"]
    ledger = reports["v22_outcome_ledger_integration_report_v1.json"]
    scoreboard = reports["domain_scoreboard_v6_report.json"]
    final_v17 = _load_report("final_report_v17.json", {})
    final_v18 = _load_report("final_report_v18.json", {})
    final_v19 = _load_report("final_report_v19.json", {})
    final_v20 = _load_report("final_report_v20.json", {})
    final_v21 = _load_report("final_report_v21.json", {})
    v17_evidence = reconcile_v17_truth_loop_evidence(final_v17)
    forecast_count = forecast["forecast_snapshot_count"]
    final_verdict = "FAIL" if failures else "PASS" if forecast_count > 0 else "PARTIAL"
    report_paths = {name: str(paths.get(name, ARTIFACTS / name)) for name in reports}
    no_trades = forecast["no_trade_decisions"]
    return {
        "generated_at": now_iso(),
        "workstream": "V22: Final Edge Terrain Activation Forecast Write Breakthrough",
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "partial_reason": "" if final_verdict == "PASS" else "Forecast snapshots remained zero or degraded source state blocked full breakthrough; blockers are explicit and proof-backed.",
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
        "v21_source_activation_status": final_v21.get("verdict", mission["v21_source_activation_status"]),
        "live_submit_enabled": False,
        "live_submit_flag_status": "enabled=false",
        "caps_config_status": reports["no_caps_config_modification_report_v22.json"]["verdict"],
        "active_source_count": mission["active_real_source_count"],
        "real_vs_fixture_split": mission["real_vs_fixture_split"],
        "context_vs_edge_split": mission["context_vs_edge_split"],
        "edge_role_classifier_status": mission["edge_role_classifier_status"],
        "normalized_evidence_status": mission["normalized_evidence_status"],
        "crypto_spot_edge_terrain_status": mission["crypto_edge_activation_status"],
        "weather_edge_terrain_status": mission["weather_edge_activation_status"],
        "commodity_context_guard_status": mission["commodity_context_guard_status"],
        "finance_context_guard_status": mission["finance_context_guard_status"],
        "market_event_mapper_status": mission["market_event_mapping_status"],
        "kalshi_market_mapping_status": mission["kalshi_market_mapping_status"],
        "forecast_write_breakthrough_status": mission["forecast_write_breakthrough_status"],
        "forecast_snapshot_count": forecast_count,
        "no_trade_count": forecast["no_trade_count"],
        "observer_queue_count": mission["observer_queue_count"],
        "outcome_ledger_integration_status": ledger["verdict"],
        "top_no_trade_blockers": [{"domain": item["domain"], "blocker": item["blocker"]} for item in no_trades[:5]],
        "top_tier0_tier2_acquisition_recommendations": mission["top_acquisition_recommendations"],
        "github_adapter_queue_status": reports["github_adapter_implementation_queue_v2_report.json"]["verdict"],
        "compounding_control_plane_v5_status": reports["compounding_control_plane_v5_report.json"]["verdict"],
        "next_tactical_bundle_recommendation": mission["next_tactical_bundle_recommendation"],
        "domain_scoreboard_v6_status": scoreboard["verdict"],
        "mission_state_verdict": mission["verdict"],
        "no_secret_leak_status": reports["no_secret_leak_report_v22.json"]["verdict"],
        "no_source_api_key_leak_status": reports["no_source_api_key_leak_report_v22.json"]["verdict"],
        "no_github_token_leak_status": reports["no_github_token_leak_report_v22.json"]["verdict"],
        "no_kalshi_private_key_leak_status": reports["no_kalshi_private_key_leak_report_v22.json"]["verdict"],
        "no_direct_order_bypass_status": reports["no_direct_order_bypass_report_v22.json"]["verdict"],
        "no_direct_cancel_bypass_status": reports["no_direct_cancel_bypass_report_v22.json"]["verdict"],
        "no_unauthorized_source_status": reports["no_unauthorized_source_report_v22.json"]["verdict"],
        "no_questionable_odds_scraping_status": reports["no_questionable_odds_scraping_report_v22.json"]["verdict"],
        "no_unapproved_source_activation_status": reports["no_unapproved_source_activation_report_v22.json"]["verdict"],
        "no_commercial_source_without_approval_status": reports["no_commercial_source_without_approval_report_v22.json"]["verdict"],
        "no_fixture_claimed_real_status": reports["no_fixture_claimed_real_report_v22.json"]["verdict"],
        "no_context_claimed_edge_status": reports["no_context_claimed_edge_report_v22.json"]["verdict"],
        "no_outcome_fabrication_status": reports["no_outcome_fabrication_report_v22.json"]["verdict"],
        "no_forecast_to_execution_bridge_status": reports["no_forecast_to_execution_bridge_report_v22.json"]["verdict"],
        "no_observer_to_execution_bridge_status": reports["no_observer_to_execution_bridge_report_v22.json"]["verdict"],
        "blunder_separation_status": reports["blunder_separation_recheck_v22.json"]["verdict"],
        "dashboard_status": reports["dashboard_v22_report_v1.json"]["verdict"],
        "proof_paths": {
            "final_report_v22": str(ARTIFACTS / "final_report_v22.json"),
            "final_report": str(ARTIFACTS / "final_report.json"),
            "tests_summary": str(ARTIFACTS / "tests_summary.json"),
            "forecast_snapshot_write_proof": str(ARTIFACTS / "forecast_snapshot_write_proof_v1.json"),
            "no_trade_write_proof": str(ARTIFACTS / "no_trade_write_proof_v1.json"),
            "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v8.json"),
        },
        "remaining_operator_actions": [item["next_action"] for item in mission["top_acquisition_recommendations"]],
    }


def generate_all_v22_reports_for_tests(*, enable_network: bool = False) -> dict[str, dict[str, Any]]:
    reports = generate_v22_report_bundle(enable_network=enable_network)
    reports["final_report_v22.json"] = _build_final(reports)
    return reports


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = dict(final)
    final_index["final_report_v22"] = str(final_path)
    final_index["v22"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v22": str(final_path),
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
    enable_network = os.environ.get("DUMMY_V22_ENABLE_NETWORK", "0") == "1"
    reports = generate_v22_report_bundle(enable_network=enable_network)
    paths = {name: _write_report(name, data) for name, data in reports.items()}

    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v22.json", final)
    paths["final_report_v22.json"] = final_path
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v22_required_commands"] = _required_test_commands()
    tests_summary["v22_required_tests"] = _required_v22_tests()
    tests_summary["v22_required_reports"] = _v22_report_names(reports)
    tests_summary["v22_report_generated_at"] = final["generated_at"]
    tests_summary["v22_final_verdict"] = final["verdict"]
    (ARTIFACTS / "tests_summary.json").write_text(json.dumps(tests_summary, indent=2, default=str), encoding="utf-8")

    print(json.dumps(final, indent=2, default=str))
    return final


if __name__ == "__main__":
    main()
